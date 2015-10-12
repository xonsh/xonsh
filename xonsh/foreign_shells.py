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
echo __XONSH_ENV_BEG__
{envcmd}
echo __XONSH_ENV_END__
echo __XONSH_ALIAS_BEG__
{aliascmd}
echo __XONSH_ALIAS_END__
""".strip()

@lru_cache()
def foreign_shell_data(shell, interactive=True, login=False, envcmd='env', 
                       aliascmd='alias', extra_args=(), currenv=None, 
                       safe=True):
    """Extracts data from a foreign (non-xonsh) shells. Currently this gets 
    the environment and aliases, but may be extended in the future.

    Parameters
    ----------
    shell : str
        The name of the shell, such as 'bash' or '/bin/sh'.
    interactive : bool, optional
        Whether the shell should be run in interactive mode.
    login : bool, optional
        Whether the shell should be a login shell.
    envcmd : str, optional
        The command to generate environment output with.
    aliascmd : str, optional
        The command to generate alais output with.
    extra_args : tuple of str, optional
        Addtional command line options to pass into the shell.
    currenv : tuple of items or None, optional
        Manual override for the current environment.
    safe : bool, optional
        Flag for whether or not to safely handle exceptions and other errors. 

    Returns
    -------
    env : dict
        Dictionary of shell's environment
    aliases : dict
        Dictionary of shell's alaiases.
    """
    cmd = [shell]
    cmd.extend(extra_args)  # needs to come here for GNU long options
    if interactive:
        cmd.append('-i')
    if login:
        cmd.append('-l')
    cmd.append('-c')
    cmd.append(COMMAND.format(envcmd=envcmd, aliascmd=aliascmd))
    if currenv is None and hasattr(builtins, '__xonsh_env__'):
        currenv = builtins.__xonsh_env__.detype()
    elif currenv is not None:
        currenv = dict(currenv)
    try:
        s = subprocess.check_output(cmd,stderr=subprocess.PIPE, env=currenv,
                                    universal_newlines=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not safe:
            raise
        return {}, {}
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


VALID_SHELL_PARAMS = frozenset(['shell', 'interactive', 'login', 'envcmd', 
                                'aliascmd', 'extra_args', 'currenv', 'safe'])

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
        shell['envcmd'] = eunsure_string(shell['envcmd'])
    if 'aliascmd' in shell_keys:
        shell['aliascmd'] = eunsure_string(shell['aliascmd'])
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
