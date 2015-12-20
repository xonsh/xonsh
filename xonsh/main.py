# -*- coding: utf-8 -*-
"""The main xonsh script."""
import os
import sys
import builtins
from argparse import ArgumentParser, ArgumentTypeError
from contextlib import contextmanager

from xonsh import __version__
from xonsh.shell import Shell
from xonsh.pretty import pprint
from xonsh.jobs import ignore_sigtstp

def path_argument(s):
    """Return a path only if the path is actually legal

    This is very similar to argparse.FileType, except that it doesn't return
    an open file handle, but rather simply validates the path."""

    s = os.path.abspath(os.path.expanduser(s))
    if not os.path.isfile(s):
        raise ArgumentTypeError('"%s" must be a valid path to a file' % s)
    return s


parser = ArgumentParser(description='xonsh')
parser.add_argument('-V', '--version',
                    action='version',
                    version='/'.join(('xonsh', __version__)),
                    help='show version information and exit')
parser.add_argument('-c',
                    help="Run a single command and exit",
                    dest='command',
                    required=False,
                    default=None)
parser.add_argument('-i',
                    help='force running in interactive mode',
                    dest='force_interactive',
                    action='store_true',
                    default=False)
parser.add_argument('-l',
                    help='run as a login shell',
                    dest='login',
                    action='store_true',
                    default=False)
parser.add_argument('--config-path',
                    help='specify a custom static configuration file',
                    dest='config_path',
                    type=path_argument)
parser.add_argument('--no-rc',
                    help="Do not load the .xonshrc file",
                    dest='norc',
                    action='store_true',
                    default=False)
parser.add_argument('-D',
                    dest='defines',
                    help='define an environment variable, in the form of '
                         '-DNAME=VAL. May be used many times.',
                    metavar='ITEM',
                    nargs='*',
                    default=None)
parser.add_argument('--shell-type',
                    help='What kind of shell should be used. '
                         'Possible options: readline, prompt_toolkit, random. '
                         'Warning! If set this overrides $SHELL_TYPE variable.',
                    dest='shell_type',
                    choices=('readline', 'prompt_toolkit', 'random'),
                    default=None)
parser.add_argument('file',
                    metavar='script-file',
                    help='If present, execute the script in script-file'
                         ' and exit',
                    nargs='?',
                    default=None)
parser.add_argument('args',
                    metavar='args',
                    help='Additional arguments to the script specified'
                         ' by script-file',
                    nargs='*',
                    default=[])


def _pprint_displayhook(value):
    if value is not None:
        builtins._ = value
        pprint(value)


def premain(argv=None):
    """Setup for main xonsh entry point, returns parsed arguments."""
    args = parser.parse_args(argv)
    shell_kwargs = {'shell_type': args.shell_type}
    if args.norc:
        shell_kwargs['ctx'] = {}
    if args.config_path:
        shell_kwargs['ctx']= {'XONSHCONFIG': args.config_path}
    setattr(sys, 'displayhook', _pprint_displayhook)
    shell = builtins.__xonsh_shell__ = Shell(**shell_kwargs)
    from xonsh import imphooks
    env = builtins.__xonsh_env__
    if args.defines is not None:
        env.update([x.split('=', 1) for x in args.defines])
    if args.login:
        env['XONSH_LOGIN'] = True
    env['XONSH_INTERACTIVE'] = False
    return args


def main(argv=None):
    """Main entry point for xonsh cli."""
    args = premain(argv)
    env = builtins.__xonsh_env__
    shell = builtins.__xonsh_shell__
    if args.command is not None:
        # run a single command and exit
        shell.default(args.command)
    elif args.file is not None:
        # run a script contained in a file
        if os.path.isfile(args.file):
            with open(args.file) as f:
                code = f.read()
            code = code if code.endswith('\n') else code + '\n'
            env['ARGS'] = [args.file] + args.args
            code = shell.execer.compile(code, mode='exec', glbs=shell.ctx)
            shell.execer.exec(code, mode='exec', glbs=shell.ctx)
        else:
            print('xonsh: {0}: No such file or directory.'.format(args.file))
    elif not sys.stdin.isatty() and not args.force_interactive:
        # run a script given on stdin
        code = sys.stdin.read()
        code = code if code.endswith('\n') else code + '\n'
        code = shell.execer.compile(code, mode='exec', glbs=shell.ctx)
        shell.execer.exec(code, mode='exec', glbs=shell.ctx)
    else:
        # otherwise, enter the shell
        env['XONSH_INTERACTIVE'] = True
        ignore_sigtstp()
        shell.cmdloop()
    postmain(args)


def postmain(args=None):
    """Teardown for main xonsh entry point, accepts parsed arguments."""
    del builtins.__xonsh_shell__


@contextmanager
def main_context(argv=None):
    """Generator that runs pre- and post-main() functions. This has two iterations.
    The first yields the shell. The second returns None but cleans
    up the shell.
    """
    args = premain(argv)
    yield builtins.__xonsh_shell__
    postmain(args)



if __name__ == '__main__':
    main()
