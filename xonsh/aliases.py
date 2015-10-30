"""Aliases for the xonsh shell."""
import os
import shlex
import builtins
import subprocess
from warnings import warn
from argparse import ArgumentParser

from xonsh.dirstack import cd, pushd, popd, dirs
from xonsh.jobs import jobs, fg, bg, kill_all_jobs
from xonsh.timings import timeit_alias
from xonsh.tools import ON_MAC, ON_WINDOWS, XonshError
from xonsh.history import main as history_alias
from xonsh.replay import main as replay_main
from xonsh.environ import locate_binary


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


def source_alias(args, stdin=None):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source instead"""
    for fname in args:
        if not os.path.isfile(fname):
            fname = locate_binary(fname, cwd=None)[:-1]
        with open(fname, 'r') as fp:
            execx(fp.read(), 'exec', builtins.__xonsh_ctx__)


def xexec(args, stdin=None):
    """Replaces current process with command specified and passes in the
    current xonsh environment.
    """
    env = builtins.__xonsh_env__
    denv = env.detype()
    if len(args) > 0:
        try:
            os.execvpe(args[0], args, denv)
        except FileNotFoundError as e:
            return 'xonsh: ' + e.args[1] + ': ' + args[0] + '\n'
    else:
        return 'xonsh: exec: no args specified\n'


_BANG_N_PARSER = None


def bang_n(args, stdin=None):
    """Re-runs the nth command as specified in the argument."""
    global _BANG_N_PARSER
    if _BANG_N_PARSER is None:
        parser = _BANG_N_PARSER = ArgumentParser('!n', usage='!n <n>',
                    description="Re-runs the nth command as specified in the argument.")
        parser.add_argument('n', type=int, help='the command to rerun, may be negative')
    else:
        parser = _BANG_N_PARSER
    ns = parser.parse_args(args)
    hist = builtins.__xonsh_history__
    nhist = len(hist)
    n = nhist + ns.n if ns.n < 0 else ns.n
    if n < 0 or n >= nhist:
        raise IndexError('n out of range, {0} for history len {1}'.format(ns.n, nhist))
    cmd = hist.inps[n]
    if cmd.startswith('!'):
        raise XonshError('xonsh: error: recursive call to !n')
    builtins.execx(cmd)


def bang_bang(args, stdin=None):
    """Re-runs the last command. Just a wrapper around bang_n."""
    return bang_n(['-1'])


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
    'source': source_alias,
    'source-bash': source_bash,
    'history': history_alias,
    'replay': replay_main,
    '!!': bang_bang,
    '!n': bang_n,
    'timeit': timeit_alias,
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
}

if ON_WINDOWS:
    # Borrow builtin commands from cmd.exe.
    WINDOWS_CMD_ALIASES = {
        'cls',
        'copy',
        'del',
        'dir',
        'erase',
        'md',
        'mkdir',
        'mklink',
        'move',
        'rd',
        'ren',
        'rename',
        'rmdir',
        'time',
        'type',
        'vol'
    }

    for alias in WINDOWS_CMD_ALIASES:
        DEFAULT_ALIASES[alias] = ['cmd', '/c', alias]

    DEFAULT_ALIASES['which'] = ['where']

elif ON_MAC:
    DEFAULT_ALIASES['ls'] = ['ls', '-G']
else:
    DEFAULT_ALIASES['grep'] = ['grep', '--color=auto']
    DEFAULT_ALIASES['ls'] = ['ls', '--color=auto', '-v']
