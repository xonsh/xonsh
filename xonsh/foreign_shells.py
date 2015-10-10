"""Tools to help interface with foreign shells, such as Bash."""
import re
import shlex
import builtins
import subprocess
from warnings import warn
from functools import lru_cache


COMMAND = """
echo __XONSH_ENV_BEG__
{envcmd}
echo __XONSH_ENV_END__
echo __XONSH_ALIAS_BEG__
{aliascmd}
echo __XONSH_ALIAS_END__
""".strip()

FAILED_COMMAND_STDOUT = """
__XONSH_ENV_BEG__
__XONSH_ENV_END__
__XONSH_ALIAS_BEG__
__XONSH_ALIAS_END__
""".strip()

@lru_cache()
def foreign_shell_data(shell, interactive=True, login=False, envcmd='env', 
                       aliascmd='alias', extra_args=(), currenv=None):
    """Extracts data from a foreign (non-xonsh) shells. Currently this gets 
    the environment and aliases, but may be extended in the future.

    Parameters
    ----------
    shell : str
        The name of the shell, such as 'bash' or '/bin/sh'.
    login : bool, optional
        Whether the shell should be run in interactive mode.
    login : bool, optional
        Whether the shell should be a login shell.
    envcmd : str, optional
        The command to generate environment output with.
    aliascmd : str, optional
        The command to generate alais output with.
    extra_args : list of str, optional
        Addtional command line options to pass into the shell.
    currenv : dict or None, optional
        Manual override for the current environment.

    Returns
    -------
    env : dict
        Dictionary of shell's environment
    aliases : dict
        Dictionary of shell's alaiases.
    """
    cmd = [shell]
    if interactive:
        cmd.append('-i')
    if login:
        cmd.append('-l')
    cmd.extend(extra_args)
    cmd.append('-c')
    cmd.append(COMMAND.format(envcmd=envcmd, aliascmd=aliascmd))
    if currenv is None and hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    try:
        s = subprocess.check_output(cmd,stderr=subprocess.PIPE, env=currenv,
                                    universal_newlines=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        s = FAILED_COMMAND_STDOUT
    env = parse_env(s)
    aliases = parse_aliases(s)
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

