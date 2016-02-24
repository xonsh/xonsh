#!/usr/bin/env xonsh
"""Release helper script for xonsh."""
import os
import re
import sys
from argparse import ArgumentParser, Action

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

NEW_DEV = """
Current Developments
====================
**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
""".strip()

def version_update(ver):
    """Updates version strings in relevant files."""
    pnfs = [
        ('__version__\s*=.*', "__version__ = '{0}'".format(ver),
         ['xonsh', '__init__.py']),
        ('version:\s*', 'version: {0}.{{build}}'.format(ver), ['.appveyor.yml']),
        ('  version:\s*.*', '  version: "{0}"'.format(ver), ['recipe', 'meta.yaml']),
        ('\*\*\w+:\*\* None', '', ['CHANGELOG.rst']),
        ('Current Developments', NEW_DEV + '\n\nv' + ver, ['CHANGELOG.rst']),
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
    conda_bld = os.path.join(conda_dir, 'conda-bld')
    rm -f @(os.path.join(conda_bld, 'src_cache', 'xonsh.tar.gz'))
    conda build --no-test recipe
    pkgpath = os.path.join(conda_bld, '*', 'xonsh-{0}*.tar.bz2'.format(ver))
    pkg = __xonsh_glob__(pkgpath)[0]
    conda convert -p all -o @(conda_bld) @(pkg)
    anaconda upload -u xonsh @(__xonsh_glob__(pkgpath))

def docser():
    """Create docs"""
    # FIXME this should be made more general
    ./setup.py install --user
    cd docs
    make clean html push-root
    cd ..


DOERS = ('do_version_bump', 'do_git', 'do_pip', 'do_conda', 'do_docs')

class OnlyAction(Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        for doer in DOERS:
            if doer == self.dest:
                setattr(namespace, doer, True)
            else:
                setattr(namespace, doer, False)


def main(args=None):
    parser = ArgumentParser('release')
    parser.add_argument('--upstream',
                        default='git@github.com:scopatz/xonsh.git',
                        help='upstream repo')
    parser.add_argument('-b', '--branch', default='master',
                         help='branch to commit / push to.')
    for doer in DOERS:
        base = doer[3:].replace('_', '-')
        parser.add_argument('--do-' + base, dest=doer, default=True,
                            action='store_true',
                            help='runs ' + base)
        parser.add_argument('--no-' + base, dest=doer, action='store_false',
                            help='does not run ' + base)
        parser.add_argument('--only-' + base, dest=doer, action=OnlyAction,
                            help='only runs ' + base, nargs=0)
    parser.add_argument('ver', help='target version string')
    ns = parser.parse_args(args or $ARGS[1:])

    # enable debugging
    $RAISE_SUBPROC_ERROR = True
    trace on

    # run commands
    if ns.do_version_bump:
        version_update(ns.ver)
    if ns.do_git:
        just_do_git(ns)
    if ns.do_pip:
        pipify()
    if ns.do_conda:
        condaify(ns.ver)
    if ns.do_docs:
        docser()

    # disable debugging
    trace off

if __name__ == '__main__':
    main()
