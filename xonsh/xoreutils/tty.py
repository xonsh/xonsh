import os
import sys


def tty(args, stdin, stdout, stderr):
    if '--help' in args:
        print(HELP_STR, file=stdout)
        return 0
    silent = False
    for i in ('-s', '--silent', '--quiet'):
        if i in args:
            silent = True
            args.remove(i)
    if len(args) > 0:
        if not silent:
            for i in args:
                print('tty: Invalid option: {}'.format(i), file=stderr)
            print("Try 'tty --help' for more information", file=stderr)
        return 2
    fd = stdin.fileno()
    if not os.isatty(fd):
        if not silent:
            print('not a tty', file=stdout)
        return 1
    if not silent:
        try:
            print(os.ttyname(fd), file=stdout)
        except:
            return 3
    return 0

HELP_STR = """This version of tty was written in Python for the xonsh project: http://xon.sh
Based on tty from GNU coreutils: http://www.gnu.org/software/coreutils/

Usage: /usr/bin/tty [OPTION]...
Print the file name of the terminal connected to standard input.

  -s, --silent, --quiet   print nothing, only return an exit status
      --help     display this help and exit"""
