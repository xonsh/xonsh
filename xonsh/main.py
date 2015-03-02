"""The main xonsh script."""
import os
import sys
import shlex
import subprocess
from argparse import ArgumentParser, Namespace

#import urwid

from xonsh.shell import Shell
from xonsh.main_display import MainDisplay

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    #disp = MainDisplay()
    #disp.main()
    shell = Shell()
    shell.cmdloop()

if __name__ == '__main__':
    main()