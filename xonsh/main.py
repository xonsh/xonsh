"""The main xonsh script."""
import os
import sys
import shlex
import signal
import builtins
import subprocess
from argparse import ArgumentParser, Namespace

from xonsh import __version__
from xonsh.shell import Shell
from xonsh.pretty import pprint
from xonsh.jobs import ignore_sigtstp

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
                         'Possible options: readline, prompt_toolkit. '
                         'Warning! If set this overrides $SHELL_TYPE variable.',
                    dest='shell_type',
                    choices=('readline', 'prompt_toolkit'),
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


def main(argv=None):
    """Main entry point for xonsh cli."""
    args = parser.parse_args()
    shell_kwargs = {'shell_type': args.shell_type}
    if args.norc:
        shell_kwargs['ctx'] = {}
    setattr(sys, 'displayhook', _pprint_displayhook)
    shell = builtins.__xonsh_shell__ = Shell(**shell_kwargs)
    from xonsh import imphooks
    env = builtins.__xonsh_env__
    if args.defines is not None:
        env.update([x.split('=', 1) for x in args.defines])
    env['XONSH_INTERACTIVE'] = False
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
    elif not sys.stdin.isatty():
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
    del builtins.__xonsh_shell__


if __name__ == '__main__':
    main()
