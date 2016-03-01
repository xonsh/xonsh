# -*- coding: utf-8 -*-
"""Aliases for the xonsh shell."""
import os
import shlex
import builtins
import subprocess
from warnings import warn
from argparse import ArgumentParser

from xonsh.dirstack import cd, pushd, popd, dirs
from xonsh.jobs import jobs, fg, bg, kill_all_jobs
from xonsh.proc import foreground
from xonsh.timings import timeit_alias
from xonsh.tools import ON_MAC, ON_WINDOWS, XonshError, to_bool
from xonsh.history import main as history_alias
from xonsh.replay import main as replay_main
from xonsh.environ import locate_binary
from xonsh.foreign_shells import foreign_shell_data
from xonsh.vox import Vox


def exit(args, stdin=None):  # pylint:disable=redefined-builtin,W0622
    """Sends signal to exit shell."""
    builtins.__xonsh_exit__ = True
    kill_all_jobs()
    print()  # gimme a newline
    return None, None


_SOURCE_FOREIGN_PARSER = None

def _ensure_source_foreign_parser():
    global _SOURCE_FOREIGN_PARSER
    if _SOURCE_FOREIGN_PARSER is not None:
        return _SOURCE_FOREIGN_PARSER
    desc = "Sources a file written in a foreign shell language."
    parser = ArgumentParser('source-foreign', description=desc)
    parser.add_argument('shell', help='Name or path to the foreign shell')
    parser.add_argument('files_or_code', nargs='+',
                        help='file paths to source or code in the target '
                             'language.')
    parser.add_argument('-i', '--interactive', type=to_bool, default=True,
                        help='whether the sourced shell should be interactive',
                        dest='interactive')
    parser.add_argument('-l', '--login', type=to_bool, default=False,
                        help='whether the sourced shell should be login',
                        dest='login')
    parser.add_argument('--envcmd', default=None, dest='envcmd',
                        help='command to print environment')
    parser.add_argument('--aliascmd', default=None, dest='aliascmd',
                        help='command to print aliases')
    parser.add_argument('--extra-args', default=(), dest='extra_args',
                        type=(lambda s: tuple(s.split())),
                        help='extra arguments needed to run the shell')
    parser.add_argument('-s', '--safe', type=to_bool, default=True,
                        help='whether the source shell should be run safely, '
                             'and not raise any errors, even if they occur.',
                        dest='safe')
    parser.add_argument('-p', '--prevcmd', default=None, dest='prevcmd',
                        help='command(s) to run before any other commands, '
                             'replaces traditional source.')
    parser.add_argument('--postcmd', default='', dest='postcmd',
                        help='command(s) to run after all other commands')
    parser.add_argument('--funcscmd', default=None, dest='funcscmd',
                        help='code to find locations of all native functions '
                             'in the shell language.')
    parser.add_argument('--sourcer', default=None, dest='sourcer',
                        help='the source command in the target shell language, '
                             'default: source.')
    _SOURCE_FOREIGN_PARSER = parser
    return parser


def source_foreign(args, stdin=None):
    """Sources a file written in a foreign shell language."""
    parser = _ensure_source_foreign_parser()
    ns = parser.parse_args(args)
    if ns.prevcmd is not None:
        pass  # don't change prevcmd if given explicitly
    elif os.path.isfile(ns.files_or_code[0]):
        # we have filename to source
        ns.prevcmd = '{0} "{1}"'.format(ns.sourcer, '" "'.join(ns.files_or_code))
    elif ns.prevcmd is None:
        ns.prevcmd = ' '.join(ns.files_or_code)  # code to run, no files
    foreign_shell_data.cache_clear()  # make sure that we don't get prev src
    fsenv, fsaliases = foreign_shell_data(shell=ns.shell, login=ns.login,
                            interactive=ns.interactive, envcmd=ns.envcmd,
                            aliascmd=ns.aliascmd, extra_args=ns.extra_args,
                            safe=ns.safe, prevcmd=ns.prevcmd,
                            postcmd=ns.postcmd, funcscmd=ns.funcscmd,
                            sourcer=ns.sourcer)
    # apply results
    env = builtins.__xonsh_env__
    denv = env.detype()
    for k, v in fsenv.items():
        if k in denv and v == denv[k]:
            continue  # no change from original
        env[k] = v
    baliases = builtins.aliases
    for k, v in fsaliases.items():
        if k in baliases and v == baliases[k]:
            continue  # no change from original
        baliases[k] = v


def source_bash(args, stdin=None):
    """Simple Bash-specific wrapper around source-foreign."""
    args = list(args)
    args.insert(0, 'bash')
    args.append('--sourcer=source')
    return source_foreign(args, stdin=stdin)


def source_zsh(args, stdin=None):
    """Simple zsh-specific wrapper around source-foreign."""
    args = list(args)
    args.insert(0, 'zsh')
    args.append('--sourcer=source')
    return source_foreign(args, stdin=stdin)


def source_alias(args, stdin=None):
    """Executes the contents of the provided files in the current context.
    If sourced file isn't found in cwd, search for file along $PATH to source instead"""
    for fname in args:
        if not os.path.isfile(fname):
            fname = locate_binary(fname)
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


def xonfig(args, stdin=None):
    """Runs the xonsh configuration utility."""
    from xonsh.xonfig import main  # lazy import
    return main(args)


@foreground
def trace(args, stdin=None):
    """Runs the xonsh tracer utility."""
    from xonsh.tracer import main  # lazy import
    return main(args)


def vox(args, stdin=None):
    """Runs Vox environment manager."""
    vox = Vox()
    return vox(args, stdin=stdin)

@foreground
def mpl(args, stdin=None):
    """Hooks to matplotlib"""
    from xonsh.mplhooks import show
    show()


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
    'source-zsh': source_zsh,
    'source-bash': source_bash,
    'source-foreign': source_foreign,
    'history': history_alias,
    'replay': replay_main,
    '!!': bang_bang,
    '!n': bang_n,
    'mpl': mpl,
    'trace': trace,
    'timeit': timeit_alias,
    'xonfig': xonfig,
    'scp-resume': ['rsync', '--partial', '-h', '--progress', '--rsh=ssh'],
    'ipynb': ['ipython', 'notebook', '--no-browser'],
    'vox': vox,
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
