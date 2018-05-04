# -*- coding: utf-8 -*-
"""Tools to help interface with foreign shells, such as Bash."""
import os
import re
import json
import shlex
import sys
import tempfile
import builtins
import subprocess
import warnings
import functools
import collections.abc as cabc

from xonsh.lazyasd import lazyobject
from xonsh.tools import to_bool, ensure_string
from xonsh.platform import ON_WINDOWS, ON_CYGWIN, ON_MSYS


COMMAND = """{seterrprevcmd}
{prevcmd}
echo __XONSH_ENV_BEG__
{envcmd}
echo __XONSH_ENV_END__
echo __XONSH_ALIAS_BEG__
{aliascmd}
echo __XONSH_ALIAS_END__
echo __XONSH_FUNCS_BEG__
{funcscmd}
echo __XONSH_FUNCS_END__
{postcmd}
{seterrpostcmd}"""

DEFAULT_BASH_FUNCSCMD = r"""# get function names from declare
declstr=$(declare -F)
read -r -a decls <<< $declstr
funcnames=""
for((n=0;n<${#decls[@]};n++)); do
  if (( $(($n % 3 )) == 2 )); then
    # get every 3rd entry
    funcnames="$funcnames ${decls[$n]}"
  fi
done

# get functions locations: funcname lineno filename
shopt -s extdebug
namelocfilestr=$(declare -F $funcnames)
shopt -u extdebug

# print just names and files as JSON object
read -r -a namelocfile <<< $namelocfilestr
sep=" "
namefile="{"
while IFS='' read -r line || [[ -n "$line" ]]; do
  name=${line%%"$sep"*}
  locfile=${line#*"$sep"}
  loc=${locfile%%"$sep"*}
  file=${locfile#*"$sep"}
  namefile="${namefile}\"${name}\":\"${file//\\/\\\\}\","
done <<< "$namelocfilestr"
if [[ "{" == "${namefile}" ]]; then
  namefile="${namefile}}"
else
  namefile="${namefile%?}}"
fi
echo $namefile"""

DEFAULT_ZSH_FUNCSCMD = """# get function names
autoload -U is-at-least  # We'll need to version check zsh
namefile="{"
for name in ${(ok)functions}; do
  # force zsh to load the func in order to get the filename,
  # but use +X so that it isn't executed.
  autoload +X $name || continue
  loc=$(whence -v $name)
  loc=${(z)loc}
  if is-at-least 5.2; then
    file=${loc[-1]}
  else
    file=${loc[7,-1]}
  fi
  namefile="${namefile}\\"${name}\\":\\"${(Q)file:A}\\","
done
if [[ "{" == "${namefile}" ]]; then
  namefile="${namefile}}"
else
  namefile="${namefile%?}}"
fi
echo ${namefile}"""


# mapping of shell name aliases to keys in other lookup dictionaries.
@lazyobject
def CANON_SHELL_NAMES():
    return {
    'bash': 'bash',
    '/bin/bash': 'bash',
    'zsh': 'zsh',
    '/bin/zsh': 'zsh',
    '/usr/bin/zsh': 'zsh',
    'cmd': 'cmd',
    'cmd.exe': 'cmd',
    }


@lazyobject
def DEFAULT_ENVCMDS():
    return {
    'bash': 'env',
    'zsh': 'env',
    'cmd': 'set',
    }


@lazyobject
def DEFAULT_ALIASCMDS():
    return {
    'bash': 'alias',
    'zsh': 'alias -L',
    'cmd': '',
    }


@lazyobject
def DEFAULT_FUNCSCMDS():
    return {
    'bash': DEFAULT_BASH_FUNCSCMD,
    'zsh': DEFAULT_ZSH_FUNCSCMD,
    'cmd': '',
    }


@lazyobject
def DEFAULT_SOURCERS():
    return {
    'bash': 'source',
    'zsh': 'source',
    'cmd': 'call',
    }


@lazyobject
def DEFAULT_TMPFILE_EXT():
    return {
    'bash': '.sh',
    'zsh': '.zsh',
    'cmd': '.bat',
    }


@lazyobject
def DEFAULT_RUNCMD():
    return {
    'bash': '-c',
    'zsh': '-c',
    'cmd': '/C',
    }


@lazyobject
def DEFAULT_SETERRPREVCMD():
    return {
    'bash': 'set -e',
    'zsh': 'set -e',
    'cmd': '@echo off',
    }


@lazyobject
def DEFAULT_SETERRPOSTCMD():
    return {
    'bash': '',
    'zsh': '',
    'cmd': 'if errorlevel 1 exit 1',
    }


@functools.lru_cache()
def foreign_shell_data(shell, interactive=True, login=False, envcmd=None,
                       aliascmd=None, extra_args=(), currenv=None,
                       safe=True, prevcmd='', postcmd='', funcscmd=None,
                       sourcer=None, use_tmpfile=False, tmpfile_ext=None,
                       runcmd=None, seterrprevcmd=None, seterrpostcmd=None,
                       show=False, dryrun=False):
    """Extracts data from a foreign (non-xonsh) shells. Currently this gets
    the environment, aliases, and functions but may be extended in the future.

    Parameters
    ----------
    shell : str
        The name of the shell, such as 'bash' or '/bin/sh'.
    interactive : bool, optional
        Whether the shell should be run in interactive mode.
    login : bool, optional
        Whether the shell should be a login shell.
    envcmd : str or None, optional
        The command to generate environment output with.
    aliascmd : str or None, optional
        The command to generate alias output with.
    extra_args : tuple of str, optional
        Additional command line options to pass into the shell.
    currenv : tuple of items or None, optional
        Manual override for the current environment.
    safe : bool, optional
        Flag for whether or not to safely handle exceptions and other errors.
    prevcmd : str, optional
        A command to run in the shell before anything else, useful for
        sourcing and other commands that may require environment recovery.
    postcmd : str, optional
        A command to run after everything else, useful for cleaning up any
        damage that the prevcmd may have caused.
    funcscmd : str or None, optional
        This is a command or script that can be used to determine the names
        and locations of any functions that are native to the foreign shell.
        This command should print *only* a JSON object that maps
        function names to the filenames where the functions are defined.
        If this is None, then a default script will attempted to be looked
        up based on the shell name. Callable wrappers for these functions
        will be returned in the aliases dictionary.
    sourcer : str or None, optional
        How to source a foreign shell file for purposes of calling functions
        in that shell. If this is None, a default value will attempt to be
        looked up based on the shell name.
    use_tmpfile : bool, optional
        This specifies if the commands are written to a tmp file or just
        parsed directly to the shell
    tmpfile_ext : str or None, optional
        If tmpfile is True this sets specifies the extension used.
    runcmd : str or None, optional
        Command line switches to use when running the script, such as
        -c for Bash and /C for cmd.exe.
    seterrprevcmd : str or None, optional
        Command that enables exit-on-error for the shell that is run at the
        start of the script. For example, this is "set -e" in Bash. To disable
        exit-on-error behavior, simply pass in an empty string.
    seterrpostcmd : str or None, optional
        Command that enables exit-on-error for the shell that is run at the end
        of the script. For example, this is "if errorlevel 1 exit 1" in
        cmd.exe. To disable exit-on-error behavior, simply pass in an
        empty string.
    show : bool, optional
        Whether or not to display the script that will be run.
    dryrun : bool, optional
        Whether or not to actually run and process the command.


    Returns
    -------
    env : dict
        Dictionary of shell's environment. (None if the subproc command fails)
    aliases : dict
        Dictionary of shell's aliases, this includes foreign function
        wrappers.(None if the subproc command fails)
    """
    cmd = [shell]
    cmd.extend(extra_args)  # needs to come here for GNU long options
    if interactive:
        cmd.append('-i')
    if login:
        cmd.append('-l')
    shkey = CANON_SHELL_NAMES[shell]
    envcmd = DEFAULT_ENVCMDS.get(shkey, 'env') if envcmd is None else envcmd
    aliascmd = DEFAULT_ALIASCMDS.get(shkey, 'alias') if aliascmd is None else aliascmd
    funcscmd = DEFAULT_FUNCSCMDS.get(shkey, 'echo {}') if funcscmd is None else funcscmd
    tmpfile_ext = DEFAULT_TMPFILE_EXT.get(shkey, 'sh') if tmpfile_ext is None else tmpfile_ext
    runcmd = DEFAULT_RUNCMD.get(shkey, '-c') if runcmd is None else runcmd
    seterrprevcmd = DEFAULT_SETERRPREVCMD.get(shkey, '') \
        if seterrprevcmd is None else seterrprevcmd
    seterrpostcmd = DEFAULT_SETERRPOSTCMD.get(shkey, '') \
        if seterrpostcmd is None else seterrpostcmd
    command = COMMAND.format(envcmd=envcmd, aliascmd=aliascmd, prevcmd=prevcmd,
                             postcmd=postcmd, funcscmd=funcscmd,
                             seterrprevcmd=seterrprevcmd,
                             seterrpostcmd=seterrpostcmd).strip()
    if show:
        print(command)
    if dryrun:
        return None, None
    cmd.append(runcmd)
    if not use_tmpfile:
        cmd.append(command)
    else:
        tmpfile = tempfile.NamedTemporaryFile(suffix=tmpfile_ext, delete=False)
        tmpfile.write(command.encode('utf8'))
        tmpfile.close()
        cmd.append(tmpfile.name)
    if currenv is None and hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    elif currenv is not None:
        currenv = dict(currenv)
    try:
        s = subprocess.check_output(cmd, stderr=subprocess.PIPE, env=currenv,
                                    # start new session to avoid hangs
                                    # (doesn't work on Cygwin though)
                                    start_new_session=((not ON_CYGWIN) and
                                                       (not ON_MSYS)),
                                    universal_newlines=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not safe:
            raise
        return None, None
    finally:
        if use_tmpfile:
            os.remove(tmpfile.name)
    env = parse_env(s)
    aliases = parse_aliases(s)
    funcs = parse_funcs(s, shell=shell, sourcer=sourcer, extra_args=extra_args)
    aliases.update(funcs)
    return env, aliases


@lazyobject
def ENV_RE():
    return re.compile('__XONSH_ENV_BEG__\n(.*)'
                      '__XONSH_ENV_END__', flags=re.DOTALL)


@lazyobject
def ENV_SPLIT_RE():
    return re.compile('^([^=]+)=([^=]*|[^\n]*)$',
                      flags=re.DOTALL | re.MULTILINE)


def parse_env(s):
    """Parses the environment portion of string into a dict."""
    m = ENV_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    g1 = g1[:-1] if g1.endswith('\n') else g1
    env = dict(ENV_SPLIT_RE.findall(g1))
    return env


@lazyobject
def ALIAS_RE():
    return re.compile('__XONSH_ALIAS_BEG__\n(.*)'
                      '__XONSH_ALIAS_END__',
                      flags=re.DOTALL)


def parse_aliases(s):
    """Parses the aliases portion of string into a dict."""
    m = ALIAS_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    items = [line.split('=', 1) for line in g1.splitlines() if
             line.startswith('alias ') and '=' in line]
    aliases = {}
    for key, value in items:
        try:
            key = key[6:]  # lstrip 'alias '
            # undo bash's weird quoting of single quotes (sh_single_quote)
            value = value.replace('\'\\\'\'', '\'')
            # strip one single quote at the start and end of value
            if value[0] == '\'' and value[-1] == '\'':
                value = value[1:-1]
            value = shlex.split(value)
        except ValueError as exc:
            warnings.warn('could not parse alias "{0}": {1!r}'.format(key, exc),
                          RuntimeWarning)
            continue
        aliases[key] = value
    return aliases


@lazyobject
def FUNCS_RE():
    return re.compile('__XONSH_FUNCS_BEG__\n(.+)\n'
                      '__XONSH_FUNCS_END__',
                      flags=re.DOTALL)


def parse_funcs(s, shell, sourcer=None, extra_args=()):
    """Parses the funcs portion of a string into a dict of callable foreign
    function wrappers.
    """
    m = FUNCS_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    if ON_WINDOWS:
        g1 = g1.replace(os.sep, os.altsep)
    try:
        namefiles = json.loads(g1.strip())
    except json.decoder.JSONDecodeError as exc:
        msg = ('{0!r}\n\ncould not parse {1} functions:\n'
               '  s  = {2!r}\n'
               '  g1 = {3!r}\n\n'
               'Note: you may be seeing this error if you use zsh with '
               'prezto. Prezto overwrites GNU coreutils functions (like echo) '
               'with its own zsh functions. Please try disabling prezto.')
        warnings.warn(msg.format(exc, shell, s, g1), RuntimeWarning)
        return {}
    sourcer = DEFAULT_SOURCERS.get(shell, 'source') if sourcer is None \
        else sourcer
    funcs = {}
    for funcname, filename in namefiles.items():
        if funcname.startswith('_') or not filename:
            continue  # skip private functions and invalid files
        if not os.path.isabs(filename):
            filename = os.path.abspath(filename)
        wrapper = ForeignShellFunctionAlias(name=funcname, shell=shell,
                                            sourcer=sourcer, filename=filename,
                                            extra_args=extra_args)
        funcs[funcname] = wrapper
    return funcs


class ForeignShellFunctionAlias(object):
    """This class is responsible for calling foreign shell functions as if
    they were aliases. This does not currently support taking stdin.
    """

    INPUT = ('{sourcer} "{filename}"\n'
             '{funcname} {args}\n')

    def __init__(self, name, shell, filename, sourcer=None, extra_args=()):
        """
        Parameters
        ----------
        name : str
            function name
        shell : str
            Name or path to shell
        filename : str
            Where the function is defined, path to source.
        sourcer : str or None, optional
            Command to source foreign files with.
        extra_args : tuple of str, optional
            Additional command line options to pass into the shell.
        """
        sourcer = DEFAULT_SOURCERS.get(shell, 'source') if sourcer is None \
            else sourcer
        self.name = name
        self.shell = shell
        self.filename = filename
        self.sourcer = sourcer
        self.extra_args = extra_args

    def __eq__(self, other):
        if not hasattr(other, 'name') or not hasattr(other, 'shell') or \
                not hasattr(other, 'filename') or not hasattr(other, 'sourcer') \
                or not hasattr(other, 'exta_args'):
            return NotImplemented
        return (self.name == other.name) and (self.shell == other.shell) and \
               (self.filename == other.filename) and \
               (self.sourcer == other.sourcer) and \
               (self.extra_args == other.extra_args)

    def __call__(self, args, stdin=None):
        args, streaming = self._is_streaming(args)
        input = self.INPUT.format(sourcer=self.sourcer, filename=self.filename,
                                  funcname=self.name, args=' '.join(args))
        cmd = [self.shell] + list(self.extra_args) + ['-c', input]
        env = builtins.__xonsh_env__
        denv = env.detype()
        if streaming:
            subprocess.check_call(cmd, env=denv)
            out = None
        else:
            out = subprocess.check_output(cmd, env=denv, stderr=subprocess.STDOUT)
            out = out.decode(encoding=env.get('XONSH_ENCODING'),
                             errors=env.get('XONSH_ENCODING_ERRORS'))
            out = out.replace('\r\n', '\n')
        return out

    def _is_streaming(self, args):
        """Test and modify args if --xonsh-stream is present."""
        if '--xonsh-stream' not in args:
            return args, False
        args = list(args)
        args.remove('--xonsh-stream')
        return args, True


@lazyobject
def VALID_SHELL_PARAMS():
    return frozenset([
    'shell', 'interactive', 'login', 'envcmd',
    'aliascmd', 'extra_args', 'currenv', 'safe',
    'prevcmd', 'postcmd', 'funcscmd', 'sourcer',
    ])


def ensure_shell(shell):
    """Ensures that a mapping follows the shell specification."""
    if not isinstance(shell, cabc.MutableMapping):
        shell = dict(shell)
    shell_keys = set(shell.keys())
    if not (shell_keys <= VALID_SHELL_PARAMS):
        msg = 'unknown shell keys: {0}'
        raise KeyError(msg.format(shell_keys - VALID_SHELL_PARAMS))
    shell['shell'] = ensure_string(shell['shell']).lower()
    if 'interactive' in shell_keys:
        shell['interactive'] = to_bool(shell['interactive'])
    if 'login' in shell_keys:
        shell['login'] = to_bool(shell['login'])
    if 'envcmd' in shell_keys:
        shell['envcmd'] = None if shell['envcmd'] is None \
            else ensure_string(shell['envcmd'])
    if 'aliascmd' in shell_keys:
        shell['aliascmd'] = None if shell['aliascmd'] is None \
            else ensure_string(shell['aliascmd'])
    if 'extra_args' in shell_keys and not isinstance(shell['extra_args'], tuple):
        shell['extra_args'] = tuple(map(ensure_string, shell['extra_args']))
    if 'currenv' in shell_keys and not isinstance(shell['currenv'], tuple):
        ce = shell['currenv']
        if isinstance(ce, cabc.Mapping):
            ce = tuple([(ensure_string(k), v) for k, v in ce.items()])
        elif isinstance(ce, cabc.Sequence):
            ce = tuple([(ensure_string(k), v) for k, v in ce])
        else:
            raise RuntimeError('unrecognized type for currenv')
        shell['currenv'] = ce
    if 'safe' in shell_keys:
        shell['safe'] = to_bool(shell['safe'])
    if 'prevcmd' in shell_keys:
        shell['prevcmd'] = ensure_string(shell['prevcmd'])
    if 'postcmd' in shell_keys:
        shell['postcmd'] = ensure_string(shell['postcmd'])
    if 'funcscmd' in shell_keys:
        shell['funcscmd'] = None if shell['funcscmd'] is None \
            else ensure_string(shell['funcscmd'])
    if 'sourcer' in shell_keys:
        shell['sourcer'] = None if shell['sourcer'] is None \
            else ensure_string(shell['sourcer'])
    if 'seterrprevcmd' in shell_keys:
        shell['seterrprevcmd'] = None if shell['seterrprevcmd'] is None \
            else ensure_string(shell['seterrprevcmd'])
    if 'seterrpostcmd' in shell_keys:
        shell['seterrpostcmd'] = None if shell['seterrpostcmd'] is None \
            else ensure_string(shell['seterrpostcmd'])
    return shell


def load_foreign_envs(shells):
    """Loads environments from foreign shells.

    Parameters
    ----------
    shells : sequence of dicts
        An iterable of dicts that can be passed into foreign_shell_data() as
        keyword arguments.

    Returns
    -------
    env : dict
        A dictionary of the merged environments.
    """
    env = {}
    for shell in shells:
        shell = ensure_shell(shell)
        shenv, _ = foreign_shell_data(**shell)
        if shenv:
            env.update(shenv)
    return env


def load_foreign_aliases(shells):
    """Loads aliases from foreign shells.

    Parameters
    ----------
    shells : sequence of dicts
        An iterable of dicts that can be passed into foreign_shell_data() as
        keyword arguments.

    Returns
    -------
    aliases : dict
        A dictionary of the merged aliases.
    """
    aliases = {}
    xonsh_aliases = builtins.aliases
    for shell in shells:
        shell = ensure_shell(shell)
        _, shaliases = foreign_shell_data(**shell)
        if not builtins.__xonsh_env__.get('FOREIGN_ALIASES_OVERRIDE'):
            shaliases = {} if shaliases is None else shaliases
            for alias in set(shaliases) & set(xonsh_aliases):
                del shaliases[alias]
                if builtins.__xonsh_env__.get('XONSH_DEBUG') > 1:
                    print('aliases: ignoring alias {!r} of shell {!r} '
                          'which tries to override xonsh alias.'
                          ''.format(alias, shell['shell']),
                          file=sys.stderr)
        aliases.update(shaliases)
    return aliases
