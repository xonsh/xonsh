# -*- coding: utf-8 -*-
"""The main xonsh script."""
import os
import sys
import enum
import argparse
import builtins
import contextlib

from xonsh import __version__
from xonsh.lazyasd import lazyobject
from xonsh.shell import Shell
from xonsh.pretty import pretty
from xonsh.proc import HiddenCompletedCommand
from xonsh.jobs import ignore_sigtstp
from xonsh.tools import setup_win_unicode_console, print_color
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS
from xonsh.codecache import run_script_with_cache, run_code_with_cache
from xonsh.xonfig import xonfig_main
from xonsh.lazyimps import pygments, pyghooks
from xonsh.imphooks import install_hook


def get_setproctitle():
    """Proxy function for loading process title"""
    try:
        from setproctitle import setproctitle as spt
    except ImportError:
        return
    return spt


def path_argument(s):
    """Return a path only if the path is actually legal

    This is very similar to argparse.FileType, except that it doesn't return
    an open file handle, but rather simply validates the path."""

    s = os.path.abspath(os.path.expanduser(s))
    if not os.path.isfile(s):
        msg = '{0!r} must be a valid path to a file'.format(s)
        raise argparse.ArgumentTypeError(msg)
    return s


@lazyobject
def parser():
    p = argparse.ArgumentParser(description='xonsh', add_help=False)
    p.add_argument('-h', '--help',
                   dest='help',
                   action='store_true',
                   default=False,
                   help='show help and exit')
    p.add_argument('-V', '--version',
                   dest='version',
                   action='store_true',
                   default=False,
                   help='show version information and exit')
    p.add_argument('-c',
                   help="Run a single command and exit",
                   dest='command',
                   required=False,
                   default=None)
    p.add_argument('-i', '--interactive',
                   help='force running in interactive mode',
                   dest='force_interactive',
                   action='store_true',
                   default=False)
    p.add_argument('-l', '--login',
                   help='run as a login shell',
                   dest='login',
                   action='store_true',
                   default=False)
    p.add_argument('--config-path',
                   help='specify a custom static configuration file',
                   dest='config_path',
                   default=None,
                   type=path_argument)
    p.add_argument('--no-rc',
                   help="Do not load the .xonshrc files",
                   dest='norc',
                   action='store_true',
                   default=False)
    p.add_argument('--no-script-cache',
                   help="Do not cache scripts as they are run",
                   dest='scriptcache',
                   action='store_false',
                   default=True)
    p.add_argument('--cache-everything',
                   help="Use a cache, even for interactive commands",
                   dest='cacheall',
                   action='store_true',
                   default=False)
    p.add_argument('-D',
                   dest='defines',
                   help='define an environment variable, in the form of '
                        '-DNAME=VAL. May be used many times.',
                   metavar='ITEM',
                   action='append',
                   default=None)
    p.add_argument('--shell-type',
                   help='What kind of shell should be used. '
                        'Possible options: readline, prompt_toolkit, random. '
                        'Warning! If set this overrides $SHELL_TYPE variable.',
                   dest='shell_type',
                   choices=('readline', 'prompt_toolkit', 'best', 'random'),
                   default=None)
    p.add_argument('file',
                   metavar='script-file',
                   help='If present, execute the script in script-file'
                        ' and exit',
                   nargs='?',
                   default=None)
    p.add_argument('args',
                   metavar='args',
                   help='Additional arguments to the script specified '
                        'by script-file',
                   nargs=argparse.REMAINDER,
                   default=[])
    return p


def _pprint_displayhook(value):
    if value is None:
        return
    builtins._ = None  # Set '_' to None to avoid recursion
    if isinstance(value, HiddenCompletedCommand):
        builtins._ = value
        return
    env = builtins.__xonsh_env__
    if env.get('PRETTY_PRINT_RESULTS'):
        printed_val = pretty(value)
    else:
        printed_val = repr(value)
    if HAS_PYGMENTS and env.get('COLOR_RESULTS'):
        tokens = list(pygments.lex(printed_val, lexer=pyghooks.XonshLexer()))
        print_color(tokens)
    else:
        print(printed_val)  # black & white case
    builtins._ = value


class XonshMode(enum.Enum):
    single_command = 0
    script_from_file = 1
    script_from_stdin = 2
    interactive = 3


def premain(argv=None):
    """Setup for main xonsh entry point, returns parsed arguments."""
    if argv is None:
        argv = sys.argv[1:]
    setproctitle = get_setproctitle()
    if setproctitle is not None:
        setproctitle(' '.join(['xonsh'] + argv))
    builtins.__xonsh_ctx__ = {}
    args = parser.parse_args(argv)
    if args.help:
        parser.print_help()
        parser.exit()
    if args.version:
        version = '/'.join(('xonsh', __version__))
        print(version)
        parser.exit()
    shell_kwargs = {'shell_type': args.shell_type,
                    'completer': False,
                    'login': False,
                    'scriptcache': args.scriptcache,
                    'cacheall': args.cacheall,
                    'ctx': builtins.__xonsh_ctx__}
    if args.login:
        shell_kwargs['login'] = True
    if args.config_path is not None:
        shell_kwargs['config'] = args.config_path
    if args.norc:
        shell_kwargs['rc'] = ()
    setattr(sys, 'displayhook', _pprint_displayhook)
    if args.command is not None:
        args.mode = XonshMode.single_command
        shell_kwargs['shell_type'] = 'none'
    elif args.file is not None:
        args.mode = XonshMode.script_from_file
        shell_kwargs['shell_type'] = 'none'
    elif not sys.stdin.isatty() and not args.force_interactive:
        args.mode = XonshMode.script_from_stdin
        shell_kwargs['shell_type'] = 'none'
    else:
        args.mode = XonshMode.interactive
        shell_kwargs['completer'] = True
        shell_kwargs['login'] = True
    install_hook()
    builtins.__xonsh_shell__ = Shell(**shell_kwargs)
    for xontrib_module in getattr(builtins.__xonsh_shell__, 'xontribs', []):
        getattr(xontrib_module, 'xontrib_init', lambda: None)()

    env = builtins.__xonsh_env__
    env['XONSH_LOGIN'] = shell_kwargs['login']
    if args.defines is not None:
        env.update([x.split('=', 1) for x in args.defines])
    env['XONSH_INTERACTIVE'] = args.force_interactive
    if ON_WINDOWS:
        setup_win_unicode_console(env.get('WIN_UNICODE_CONSOLE', True))
    return args


def main(argv=None):
    """Main entry point for xonsh cli."""
    if argv is None:
        argv = sys.argv[1:]
    args = premain(argv)
    env = builtins.__xonsh_env__
    shell = builtins.__xonsh_shell__
    if args.mode == XonshMode.interactive:
        # enter the shell
        env['XONSH_INTERACTIVE'] = True
        ignore_sigtstp()
        if (env['XONSH_INTERACTIVE'] and
                not env['LOADED_CONFIG'] and
                not any(os.path.isfile(i) for i in env['XONSHRC'])):
            print('Could not find xonsh configuration or run control files.',
                  file=sys.stderr)
            xonfig_main(['wizard', '--confirm'])
        shell.shell.cmdloop()
    elif args.mode == XonshMode.single_command:
        # run a single command and exit
        run_code_with_cache(args.command.lstrip(), shell.execer, mode='single')
    elif args.mode == XonshMode.script_from_file:
        # run a script contained in a file
        path = os.path.abspath(os.path.expanduser(args.file))
        if os.path.isfile(path):
            sys.argv = [args.file] + args.args
            env['ARGS'] = sys.argv[:]  # $ARGS is not sys.argv
            env['XONSH_SOURCE'] = path
            run_script_with_cache(args.file, shell.execer, glb=shell.ctx,
                                  loc=None, mode='exec')
        else:
            print('xonsh: {0}: No such file or directory.'.format(args.file))
    elif args.mode == XonshMode.script_from_stdin:
        # run a script given on stdin
        code = sys.stdin.read()
        run_code_with_cache(code, shell.execer, glb=shell.ctx, loc=None,
                            mode='exec')
    postmain(args)


def postmain(args=None):
    """Teardown for main xonsh entry point, accepts parsed arguments."""
    if ON_WINDOWS:
        setup_win_unicode_console(enable=False)
    if hasattr(builtins, '__xonsh_shell__'):
        del builtins.__xonsh_shell__


@contextlib.contextmanager
def main_context(argv=None):
    """Generator that runs pre- and post-main() functions. This has two iterations.
    The first yields the shell. The second returns None but cleans
    up the shell.
    """
    args = premain(argv)
    yield builtins.__xonsh_shell__
    postmain(args)
