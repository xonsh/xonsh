"""The main xonsh script."""
import os
import sys
import shlex
import subprocess
from argparse import ArgumentParser, Namespace

from xonsh.shell import Shell

def main(argv=None):
    """Main entry point for xonsh cli."""
    if argv is None:
        argv = sys.argv[1:]

    mode = 'shell'

    if '-c' in argv:
        mode = 'command'
        argv.remove('-c')

    shell = Shell()
    if mode == 'shell':
        shell.cmdloop()
    else:
        shell.default(' '.join(argv))

if __name__ == '__main__':
    main()
