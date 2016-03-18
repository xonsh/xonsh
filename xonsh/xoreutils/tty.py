import os
import sys


def tty(args, stdin, stdout, stderr):
    print(os.ttyname(sys.stdout.fileno()), file=stdout)
    return 0
