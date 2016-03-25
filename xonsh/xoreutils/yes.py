import os
import sys


def yes(args, stdin, stdout, stderr, controller):
    if '--help' in args:
        print(HELP_STR, file=stdout)
        return 0

    to_print = ["y"] if len(args) == 0 else [str(i) for i in args]

    while True:
        if controller.is_killed:
            break
        print(*to_print, file=stdout)

    return 0


HELP_STR = """This version of yes was written in Python for the xonsh project: http://xon.sh
Based on yes from GNU coreutils: http://www.gnu.org/software/coreutils/

Usage: /usr/bin/yes [STRING]...
  or:  /usr/bin/yes OPTION
Repeatedly output a line with all specified STRING(s), or 'y'.

      --help     display this help and exit"""
