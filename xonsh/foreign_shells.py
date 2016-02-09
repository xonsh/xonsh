# -*- coding: utf-8 -*-
"""Tools to help interface with foreign shells, such as Bash."""
import os
import re
import json
import shlex
import builtins
import subprocess
from warnings import warn
from functools import lru_cache
from collections import MutableMapping, Mapping, Sequence

from xonsh.tools import to_bool, ensure_string


COMMAND = """
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
""".strip()

DEFAULT_BASH_FUNCSCMD = """
# get function names from declare
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
  namefile="${namefile}\\"${name}\\":\\"${file//\\/\\\\}\\","
done <<< "$namelocfilestr"
if [[ "{" == "${namefile}" ]]; then
  namefile="${namefile}}"
else
  namefile="${namefile%?}}"
fi
echo $namefile
""".strip()

DEFAULT_ZSH_FUNCSCMD = """
namefile="{"
for name in ${(ok)functions}; do
  loc=$(whence -v $name)
  loc=${(z)loc}
  file=${loc[7,-1]}
  namefile="${namefile}\\"${name}\\":\\"${(Q)file:A}\\","
done 
if [[ "{" == "${namefile}" ]]; then
  namefile="${namefile}}"
else
  namefile="${namefile%?}}"
fi
echo ${namefile}
""".strip()

DEFAULT_ENVCMDS = {
    'bash': 'env',
    '/bin/bash': 'env',
    'zsh': 'env',
    '/bin/zsh': 'env',
    '/usr/bin/zsh': 'env',
}
DEFAULT_ALIASCMDS = {
    'bash': 'alias',
    '/bin/bash': 'alias',
    'zsh': 'alias -L',
    '/bin/zsh': 'alias -L',
    '/usr/bin/zsh': 'alias -L',
}
DEFAULT_FUNCSCMDS = {
    'bash': DEFAULT_BASH_FUNCSCMD,
    '/bin/bash': DEFAULT_BASH_FUNCSCMD,
    'zsh': DEFAULT_ZSH_FUNCSCMD,
    '/bin/zsh': DEFAULT_ZSH_FUNCSCMD,
    '/usr/bin/zsh': DEFAULT_ZSH_FUNCSCMD,
}
DEFAULT_SOURCERS = {
    'bash': 'source',
    '/bin/bash': 'source',
    'zsh': 'source',
    '/bin/zsh': 'source',
    '/usr/bin/zsh': 'source',
}

@lru_cache()
def foreign_shell_data(shell, interactive=True, login=False, envcmd=None,
                       aliascmd=None, extra_args=(), currenv=None,
                       safe=True, prevcmd='', postcmd='', funcscmd=None,
                       sourcer=None):
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
        Addtional command line options to pass into the shell.
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

    Returns
    -------
    env : dict
        Dictionary of shell's environment
    aliases : dict
        Dictionary of shell's alaiases, this includes foreign function
        wrappers.
    """
    cmd = [shell]
    cmd.extend(extra_args)  # needs to come here for GNU long options
    if interactive:
        cmd.append('-i')
    if login:
        cmd.append('-l')
    cmd.append('-c')
    envcmd = DEFAULT_ENVCMDS.get(shell, 'env') if envcmd is None else envcmd
    aliascmd = DEFAULT_ALIASCMDS.get(shell, 'alias') if aliascmd is None else aliascmd
    funcscmd = DEFAULT_FUNCSCMDS.get(shell, 'echo {}') if funcscmd is None else funcscmd
    command = COMMAND.format(envcmd=envcmd, aliascmd=aliascmd, prevcmd=prevcmd,
                             postcmd=postcmd, funcscmd=funcscmd).strip()
    cmd.append(command)
    if currenv is None and hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    elif currenv is not None:
        currenv = dict(currenv)
    try:
        s = subprocess.check_output(cmd, stderr=subprocess.PIPE, env=currenv,
                                    # start new session to avoid hangs
                                    start_new_session=True,
                                    universal_newlines=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not safe:
            raise
        return {}, {}
    env = parse_env(s)
    aliases = parse_aliases(s)
    funcs = parse_funcs(s, shell=shell, sourcer=sourcer)
    aliases.update(funcs)
    return env, aliases


ENV_RE = re.compile('__XONSH_ENV_BEG__\n(.*)__XONSH_ENV_END__', flags=re.DOTALL)

def parse_env(s):
    """Parses the environment portion of string into a dict."""
    m = ENV_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    items = [line.split('=', 1) for line in g1.splitlines() if '=' in line]
    env = dict(items)
    return env


ALIAS_RE = re.compile('__XONSH_ALIAS_BEG__\n(.*)__XONSH_ALIAS_END__',
                      flags=re.DOTALL)

def parse_aliases(s):
    """Parses the aliases portion of string into a dict."""
    m = ALIAS_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    items = [line.split('=', 1) for line in g1.splitlines() if \
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
            warn('could not parse alias "{0}": {1!r}'.format(key, exc),
                 RuntimeWarning)
            continue
        aliases[key] = value
    return aliases


FUNCS_RE = re.compile('__XONSH_FUNCS_BEG__\n(.*)__XONSH_FUNCS_END__',
                      flags=re.DOTALL)

def parse_funcs(s, shell, sourcer=None):
    """Parses the funcs portion of a string into a dict of callable foreign
    function wrappers.
    """
    m = FUNCS_RE.search(s)
    if m is None:
        return {}
    g1 = m.group(1)
    try:
        namefiles = json.loads(g1.strip())
    except json.decoder.JSONDecodeError as exc:
        msg = ('{0!r}\n\ncould not parse {1} functions:\n'
               '  s  = {2!r}\n'
               '  g1 = {3!r}\n\n'
               'Note: you may be seeing this error if you use zsh with '
               'prezto. Prezto overwrites GNU coreutils functions (like echo) '
               'with its own zsh functions. Please try disabling prezto.')
        warn(msg.format(exc, shell, s, g1), RuntimeWarning)
        return {}
    sourcer = DEFAULT_SOURCERS.get(shell, 'source') if sourcer is None \
                                                    else sourcer
    funcs = {}
    for funcname, filename in namefiles.items():
        if funcname.startswith('_'):
            continue  # skip private functions
        if not os.path.isabs(filename):
            filename = os.path.abspath(filename)
        wrapper = ForeignShellFunctionAlias(name=funcname, shell=shell,
                                            sourcer=sourcer, filename=filename)
        funcs[funcname] = wrapper
    return funcs


class ForeignShellFunctionAlias(object):
    """This class is responsible for calling foreign shell functions as if
    they were aliases. This does not currently support taking stdin.
    """

    INPUT = ('{sourcer} "{filename}"\n'
             '{funcname} {args}\n')

    def __init__(self, name, shell, filename, sourcer=None):
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
            Command to source foreing files with.
        """
        sourcer = DEFAULT_SOURCERS.get(shell, 'source') if sourcer is None \
                                                        else sourcer
        self.name = name
        self.shell = shell
        self.filename = filename
        self.sourcer = sourcer

    def __eq__(self, other):
        if not hasattr(other, 'name') or not hasattr(other, 'shell') or \
           not hasattr(other, 'filename') or not hasattr(other, 'sourcer'):
            return NotImplemented
        return (self.name == other.name) and (self.shell == other.shell) and \
               (self.filename == other.filename) and (self.sourcer == other.sourcer)

    def __call__(self, args, stdin=None):
        args, streaming = self._is_streaming(args)
        input = self.INPUT.format(sourcer=self.sourcer, filename=self.filename,
                                  funcname=self.name, args=' '.join(args))
        cmd = [self.shell, '-c', input]
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


VALID_SHELL_PARAMS = frozenset(['shell', 'interactive', 'login', 'envcmd',
                                'aliascmd', 'extra_args', 'currenv', 'safe',
                                'prevcmd', 'postcmd', 'funcscmd', 'sourcer'])

def ensure_shell(shell):
    """Ensures that a mapping follows the shell specification."""
    if not isinstance(shell, MutableMapping):
        shell = dict(shell)
    shell_keys = set(shell.keys())
    if not (shell_keys <= VALID_SHELL_PARAMS):
        msg = 'unknown shell keys: {0}'
        raise KeyError(msg.format(shell_keys - VALID_SHELL_PARAMS))
    shell['shell'] = ensure_string(shell['shell'])
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
        if isinstance(ce, Mapping):
            ce = tuple([(ensure_string(k), v) for k, v in ce.items()])
        elif isinstance(ce, Sequence):
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
    return shell


DEFAULT_SHELLS = ({'shell': 'bash'},)

def _get_shells(shells=None, config=None, issue_warning=True):
    if shells is not None and config is not None:
        raise RuntimeError('Only one of shells and config may be non-None.')
    elif shells is not None:
        pass
    else:
        if config is None:
            config = builtins.__xonsh_env__.get('XONSHCONFIG')
        if os.path.isfile(config):
            with open(config, 'r') as f:
                conf = json.load(f)
            shells = conf.get('foreign_shells', DEFAULT_SHELLS)
        else:
            if issue_warning:
                msg = 'could not find xonsh config file ($XONSHCONFIG) at {0!r}'
                warn(msg.format(config), RuntimeWarning)
            shells = DEFAULT_SHELLS
    return shells


def load_foreign_envs(shells=None, config=None, issue_warning=True):
    """Loads environments from foreign shells.

    Parameters
    ----------
    shells : sequence of dicts, optional
        An iterable of dicts that can be passed into foreign_shell_data() as
        keyword arguments. Not compatible with config not being None.
    config : str of None, optional
        Path to the static config file. Not compatible with shell not being None.
        If both shell and config is None, then it will be read from the
        $XONSHCONFIG environment variable.
    issue_warning : bool, optional
        Issues warnings if config file cannot be found.

    Returns
    -------
    env : dict
        A dictionary of the merged environments.
    """
    shells = _get_shells(shells=shells, config=config, issue_warning=issue_warning)
    env = {}
    for shell in shells:
        shell = ensure_shell(shell)
        shenv, _ = foreign_shell_data(**shell)
        env.update(shenv)
    return env


def load_foreign_aliases(shells=None, config=None, issue_warning=True):
    """Loads aliases from foreign shells.

    Parameters
    ----------
    shells : sequence of dicts, optional
        An iterable of dicts that can be passed into foreign_shell_data() as
        keyword arguments. Not compatible with config not being None.
    config : str of None, optional
        Path to the static config file. Not compatible with shell not being None.
        If both shell and config is None, then it will be read from the
        $XONSHCONFIG environment variable.
    issue_warning : bool, optional
        Issues warnings if config file cannot be found.

    Returns
    -------
    aliases : dict
        A dictionary of the merged aliases.
    """
    shells = _get_shells(shells=shells, config=config, issue_warning=issue_warning)
    aliases = {}
    for shell in shells:
        shell = ensure_shell(shell)
        _, shaliases = foreign_shell_data(**shell)
        aliases.update(shaliases)
    return aliases
