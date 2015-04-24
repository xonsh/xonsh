"""Aliases for the xonsh shell.
"""
import os
import sys
import platform
import builtins
import subprocess
import shlex
import datetime
from warnings import warn

from xonsh.dirstack import cd, pushd, popd, dirs
from xonsh.jobs import jobs, fg, bg, kill_all_jobs


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
            return 'xonsh: ' + e.args[1] + ': ' + args[0] + '\n'
    else:
        return 'xonsh: exec: no args specified\n'


def history(args, stdin=None):
    """
    Prints last n commands executed  in the format timestamp: command.

    usage: history [n], where n is an optional number of commands to print.
    """
    num = 10
    if len(args) > 0:
        try:
            num = int(args[0])
        except ValueError:
            return 'xonsh: history: usage: history [-r] [number]'
    hist_str = ''
    reversed_history = reversed(builtins.ordered_history)
    # Skip this command in history
    next(reversed_history)
    for i in range(num):
        try:
            entry = next(reversed_history)
        except StopIteration:
            break 
        timestamp = datetime.datetime.fromtimestamp(int(entry['timestamp'])
                    ).strftime('%Y-%m-%d %H:%M:%S') + ": " 
        cmd = '\033[1m' + entry['cmd'].rstrip() + '\033[0m'
        cmd = cmd.replace('\n', '\n' + ' '*len(timestamp) + ' ') + '\n'
        hist_str += '{} {}'.format(timestamp, cmd)
    return hist_str


def bang_bang(args, stdin=None):
    """
    Re-runs the last command. Just a wrapper around bang_n.
    """
    return bang_n(['1'])


def bang_n(args, stdin=None):
    """
    Re-runs the nth command as specified in the argument.
    """
    if len(args) == 1:
        try:
            # 1 is subtracted here to exclude the current command
            index = -int(args[0])-1
        except:
            return 'xonsh: !n: usage: !n n\n'
        if len(builtins.ordered_history) >= abs(index):
            cmd = builtins.ordered_history[index]['cmd']
            if '!!' not in cmd and '!n' not in cmd:
                builtins.execx(builtins.ordered_history[index]['cmd'])
            else:
                return 'xonsh: error: recursive call to !! or !n\n'
        else:
            return 'xonsh: no previous command\n'
    else:
        return 'xonsh: !n: usage: !n n\n'


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
    'history': history,
    '!!': bang_bang,
    '!n': bang_n,
    'source-bash': source_bash,
    'grep': ['grep', '--color=auto'],
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
}

if platform.system() == 'Darwin':
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
