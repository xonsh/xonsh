"""Aliases for the xonsh shell.
"""
import os
import shlex
import builtins
import subprocess
from warnings import warn

from xonsh.dirstack import cd, pushd, popd, dirs
from xonsh.jobs import jobs, fg, bg, kill_all_jobs
from xonsh.timings import timeit_alias
from xonsh.tools import ON_MAC, ON_WINDOWS


def exit(args, stdin=None):  # pylint:disable=redefined-builtin,W0622
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    kill_all_jobs()
    print()  # gimme a newline
    return None, None


def source_bash(args, stdin=None):
    """Implements bash's source builtin."""
    import tempfile
    env = builtins.__xonsh_env__
    denv = env.detype()
    with tempfile.NamedTemporaryFile(mode='w+t') as f:
        args = ' '.join(args)
        inp = 'source {0}\nenv >> {1}\n'.format(args, f.name)
        try:
            subprocess.check_output(['bash'],
                                    input=inp,
                                    env=denv,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        except subprocess.CalledProcessError:
            return None, 'could not source {0}\n'.format(args)
        f.seek(0)
        exported = f.read()
    items = [l.split('=', 1) for l in exported.splitlines() if '=' in l]
    newenv = dict(items)
    for k, v in newenv.items():
        if k in env and v == denv[k]:
            continue  # no change from original
        env[k] = v
    return


def xexec(args, stdin=None):
    """
    Replaces current process with command specified and passes in the
    current xonsh environment.
    """
    env = builtins.__xonsh_env__
    denv = env.detype()
    if (len(args) > 0):
        try:
            os.execvpe(args[0], args, denv)
        except FileNotFoundError as e:
            return "xonsh: " + e.args[1] + ": " + args[0] + "\n"
    else:
        return "xonsh: exec: no args specified\n"


def bash_aliases():
    """Computes a dictionary of aliases based on Bash's aliases."""
    try:
        s = subprocess.check_output(['bash', '-i'],
                                    input='alias',
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError:
        s = ''
    items = [line.split('=', 1) for line in s.splitlines() if '=' in line]
    aliases = {}
    for key, value in items:
        try:
            key = key[6:]
            value = value.strip('\'')
            value = shlex.split(value)
        except ValueError as exc:
            warn('could not parse Bash alias "{0}": {1!r}'.format(key, exc),
                 RuntimeWarning)
            continue
        aliases[key] = value
    return aliases


DEFAULT_ALIASES = {
    'cd': cd,
    'pushd': pushd,
    'popd': popd,
    'dirs': dirs,
    'jobs': jobs,
    'fg': fg,
    'bg': bg,
    'EOF': exit,
    'exit': exit,
    'quit': exit,
    'xexec': xexec,
    'timeit': timeit_alias,
    'source-bash': source_bash,
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
}

if ON_WINDOWS:
    DEFAULT_ALIASES['xdir'] = ['cmd', '/c', 'dir']
else:
    DEFAULT_ALIASES['xdir'] = ['/bin/dir']
    DEFAULT_ALIASES['grep'] = ['grep', '--color=auto']

if ON_MAC:
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']


