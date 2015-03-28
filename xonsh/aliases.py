"""Aliases for the xonsh shell.
"""
import os
import platform
import builtins
import subprocess
import shlex
import signal
from warnings import warn

from xonsh.dirstack import dirs, pushd, popd
from xonsh.jobs import jobs, fg, bg, kill_all_jobs

def cd(args, stdin=None):
    """Changes the directory.

    If no directory is specified (i.e. if `args` is None) then this
    changes to the current user's home directory.
    """
    env = builtins.__xonsh_env__
    cur_oldpwd = env.get('OLDPWD', os.getcwd())
    if len(args) == 0:
        d = os.path.expanduser('~')
    elif len(args) == 1:
        d = os.path.expanduser(args[0])
        if d == '-':
            d = cur_oldpwd
    else:
        return '', 'cd takes 0 or 1 arguments, not {0}\n'.format(len(args))
    if not os.path.exists(d):
        return '', 'cd: no such file or directory: {0}\n'.format(d)
    if not os.path.isdir(d):
        return '', 'cd: {0} is not a directory\n'.format(d)

    env['OLDPWD'] = os.getcwd()
    os.chdir(d)
    env['PWD'] = os.getcwd()
    return None, None


def exit(args, stdin=None):
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
        input = 'source {0}\nenv >> {1}\n'.format(args, f.name)
        try:
            subprocess.check_output(['bash'], input=input, env=denv,
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


def bash_aliases():
    """Computes a dictionary of aliases based on Bash's aliases."""
    try:
        s = subprocess.check_output(['bash', '-i'], input='alias',
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
    'source-bash': source_bash,
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
    }

if platform.system() == 'Darwin':
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
