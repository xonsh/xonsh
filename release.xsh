#!/usr/bin/env xonsh 
"""Release helper script for xonsh."""
import os
import re
import sys
from argparse import ArgumentParser

def replace_in_file(pattern, new, fname):
    """Replaces a given pattern in a file"""
    with open(fname, 'r') as f:
        raw = f.read()
    lines = raw.splitlines()
    ptn = re.compile(pattern)
    for i, line in enumerate(lines):
        if ptn.match(line):
            lines[i] = new
    upd = '\n'.join(lines) + '\n'
    with open(fname, 'w') as f:
        f.write(upd)


def version_update(ver):
    pnfs = [
        ('__version__\s*=.*', "__version__ = '{0}'".format(ver), 
         ['xonsh', '__init__.py']),
      ]
    for p, n, f in pnfs:
        replace_in_file(p, n, os.path.join(*f))


def main(args=None):
    parser = ArgumentParser('release')
    parser.add_argument('-d', action='store_true', default=False, 
                        help='dry run')
    parser.add_argument('ver', help='target version string')
    ns = parser.parse_args(args or $ARGS[1:])

    print(sys.argv)
    version_update(ns.ver)

if __name__ == '__main__':
    main()
