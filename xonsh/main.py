"""The main xonsh script."""
import os
import sys
import shlex
import subprocess
from argparse import ArgumentParser, Namespace

from xonsh.shell import Shell

parser = ArgumentParser(description='xonsh')
parser.add_argument('-c', 
        help="Run a single command and exit", 
        dest='command', 
        required=False, 
        default=None)

def main(argv=None):
    """Main entry point for xonsh cli."""

    args = parser.parse_args()

    shell = Shell()

    if args.command is None:
        shell.cmdloop()
    else:
        shell.default(args.command)

if __name__ == '__main__':
    main()
