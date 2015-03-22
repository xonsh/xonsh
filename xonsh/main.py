"""The main xonsh script."""
import os
import sys
import shlex
import subprocess
from argparse import ArgumentParser, Namespace

from xonsh.shell import Shell, builtins

parser = ArgumentParser(description='xonsh')
parser.add_argument('-c', 
        help="Run a single command and exit", 
        dest='command', 
        required=False, 
        default=None)
parser.add_argument('file',
        metavar='script-file',
        help='If present, execute the script contained in script-file and exit',
        nargs='?',
        default=None)
parser.add_argument('args',
        metavar='args',
        nargs='*',
        default=[])


def main(argv=None):
    """Main entry point for xonsh cli."""

    args = parser.parse_args()

    shell = Shell()

    env = builtins.__xonsh_env__

    if args.command is not None:
        # run a single command and exit
        shell.default(args.command)
    elif args.file is not None:
        # run a script contained in a file
        if os.path.isfile(args.file):
            with open(args.file) as f:
                code = f.read()
            code = code if code.endswith('\n') else code + '\n'
            env['0'] = args.file
            for ix, arg in enumerate(args.args):
                env[str(ix+1)] = arg
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
        shell.cmdloop()

if __name__ == '__main__':
    main()
