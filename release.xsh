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
    """Updates version strings in relevant files."""
    pnfs = [
        ('__version__\s*=.*', "__version__ = '{0}'".format(ver), 
         ['xonsh', '__init__.py']),
        ('version:\s*', 'version: {0}.{{build}}'.format(ver), '.appveyor.yml'),
      ]
    for p, n, f in pnfs:
        replace_in_file(p, n, os.path.join(*f))


def just_do_git(ns):
    """Commits and updates tags."""
    git status
    git commit -am @("version bump to " + ns.ver)
    git push @(ns.upstream) @(ns.branch)
    git tag @(ns.ver)
    git push --tags @(ns.upstream)


def pipify():
    """Make and upload pip package."""
    ./setup.py sdist upload


def condaify(ver):
    """Make and upload conda packages."""
    conda_dir = os.path.dirname(os.path.dirname($(which conda)))
    conda_bld = os.path.join(conad_dir, 'conda-bld')
    rm -f @(os.path.join(conda_bld, 'src_cache', 'xonsh.tar.gz'))
    conda build --no-test recipe
    pkgpath = os.path.join(conda_bld, '*', 'xonsh-{0}*.tar.bz2'.format(ver))
    pkg = __xonsh_glob__(pkgpath)[0]
    conda convert -p all -o @(conda_bld) @(pkg)
    anaconda upload @(pkgpath)

def docer():
    cd docs
    make clean html push-root
    cd ..


def main(args=None):
    parser = ArgumentParser('release')
    parser.add_argument('-d', action='store_true', default=False, 
                        help='dry run')
    parser.add_argument('--upstream', 
                        default='git@github.com:scopatz/xonsh.git', 
                        help='upstream repo')
    parser.add_arguement('-b', '--branch', default='master', 
                         help='branch to commit / push to.')
    parser.add_argument('ver', help='target version string')
    ns = parser.parse_args(args or $ARGS[1:])

    version_update(ns.ver)
    just_do_git(ns)
    pipify()
    condaify(ns.ver)
    docer()

if __name__ == '__main__':
    main()
