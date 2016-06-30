#!/usr/bin/env python
# -*- coding: ascii -*-
"""The xonsh installer."""
# Note: Do not embed any non-ASCII characters in this file until pip has been
# fixed. See https://github.com/xonsh/xonsh/issues/487.
from __future__ import print_function, unicode_literals
import os
import sys
import json
import subprocess

try:
    from tempfile import TemporaryDirectory
except ImportError:
    pass

try:
    from setuptools import setup
    from setuptools.command.sdist import sdist
    from setuptools.command.install import install
    from setuptools.command.develop import develop
    from setuptools.command.install_scripts import install_scripts
    HAVE_SETUPTOOLS = True
except ImportError:
    from distutils.core import setup
    from distutils.command.sdist import sdist as sdist
    from distutils.command.install import install as install
    from distutils.command.install_scripts import install_scripts
    HAVE_SETUPTOOLS = False

try:
    from jupyter_client.kernelspec import KernelSpecManager
    HAVE_JUPYTER = True
except ImportError:
    HAVE_JUPYTER = False


TABLES = ['xonsh/lexer_table.py', 'xonsh/parser_table.py', 'xonsh/__amalgam__.py']


def clean_tables():
    """Remove the lexer/parser modules that are dynamically created."""
    for f in TABLES:
        if os.path.isfile(f):
            os.remove(f)
            print('Removed ' + f)


os.environ['XONSH_DEBUG'] = '1'
from xonsh import __version__ as XONSH_VERSION

def amalagamate_source():
    """Amalgamtes source files."""
    try:
        import amalgamate
    except ImportError:
        print('Could not import amalgamate, skipping.', file=sys.stderr)
        return
    amalgamate.main(['amalgamate', '--debug=XONSH_DEBUG', 'xonsh'])


def build_tables():
    """Build the lexer/parser modules."""
    print('Building lexer and parser tables.')
    sys.path.insert(0, os.path.dirname(__file__))
    from xonsh.parser import Parser
    Parser(lexer_table='lexer_table', yacc_table='parser_table',
           outputdir='xonsh')
    amalagamate_source()
    sys.path.pop(0)


def install_jupyter_hook(prefix=None, root=None):
    """Make xonsh available as a Jupyter kernel."""
    if not HAVE_JUPYTER:
        print('Could not install Jupyter kernel spec, please install '
              'Jupyter/IPython.')
        return
    spec = {"argv": [sys.executable, "-m", "xonsh.jupyter_kernel",
                     "-f", "{connection_file}"],
            "display_name": "Xonsh",
            "language": "xonsh",
            "codemirror_mode": "shell",
           }
    with TemporaryDirectory() as d:
        os.chmod(d, 0o755)  # Starts off as 700, not user readable
        if sys.platform == 'win32':
            # Ensure that conda-build detects the hard coded prefix
            spec['argv'][0] = spec['argv'][0].replace(os.sep, os.altsep)
        with open(os.path.join(d, 'kernel.json'), 'w') as f:
            json.dump(spec, f, sort_keys=True)
        if 'CONDA_BUILD' in os.environ:
            prefix = sys.prefix
            if sys.platform == 'win32':
                prefix = prefix.replace(os.sep, os.altsep)
        user = ('--user' in sys.argv)
        print('Installing Jupyter kernel spec:')
        print('  root: {0!r}'.format(root))
        print('  prefix: {0!r}'.format(prefix))
        print('  as user: {0}'.format(user))
        KernelSpecManager().install_kernel_spec(
            d, 'xonsh', user=user, replace=True, prefix=prefix)


def dirty_version():
    """
    If install/sdist is run from a git directory (not a conda install), add
    a devN suffix to reported version number and write a gitignored file
    that holds the git hash of the current state of the repo to be queried
    by ``xonfig``
    """
    try:
        _version = subprocess.check_output(['git', 'describe', '--tags'])
    except Exception:
        print('failed to find git tags', file=sys.stderr)
        return False
    _version = _version.decode('ascii')
    try:
        base, N, sha = _version.strip().split('-')
    except ValueError: # on base release
        open('xonsh/dev.githash', 'w').close()
        print('failed to parse git version', file=sys.stderr)
        return False
    replace_version(base, N)
    with open('xonsh/dev.githash', 'w') as f:
        f.write(sha)
    print('wrote git version: ' + sha, file=sys.stderr)
    return True


ORIGINAL_VERSION_LINE = None

def replace_version(base, N):
    """Replace version in `__init__.py` with devN suffix"""
    global ORIGINAL_VERSION_LINE
    with open('xonsh/__init__.py', 'r') as f:
        raw = f.read()
    lines = raw.splitlines()
    ORIGINAL_VERSION_LINE = lines[0]
    lines[0] = "__version__ = '{}.dev{}'".format(base, N)
    upd = '\n'.join(lines) + '\n'
    with open('xonsh/__init__.py', 'w') as f:
        f.write(upd)


def restore_version():
    """If we touch the version in __init__.py discard changes after install."""
    with open('xonsh/__init__.py', 'r') as f:
        raw = f.read()
    lines = raw.splitlines()
    lines[0] = ORIGINAL_VERSION_LINE
    upd = '\n'.join(lines) + '\n'
    with open('xonsh/__init__.py', 'w') as f:
        f.write(upd)


class xinstall(install):
    """Xonsh specialization of setuptools install class."""
    def run(self):
        clean_tables()
        build_tables()
        # add dirty version number
        dirty = dirty_version()
        # install Jupyter hook
        root = self.root if self.root else None
        prefix = self.prefix if self.prefix else None
        try:
            install_jupyter_hook(prefix=prefix, root=root)
        except Exception:
            import traceback
            traceback.print_exc()
            print('Installing Jupyter hook failed.')
        install.run(self)
        if dirty:
            restore_version()



class xsdist(sdist):
    """Xonsh specialization of setuptools sdist class."""
    def make_release_tree(self, basedir, files):
        clean_tables()
        build_tables()
        dirty = dirty_version()
        sdist.make_release_tree(self, basedir, files)
        if dirty:
            restore_version()


#-----------------------------------------------------------------------------
# Hack to overcome pip/setuptools problem on Win 10.  See:
#   https://github.com/tomduck/pandoc-eqnos/issues/6
#   https://github.com/pypa/pip/issues/2783

# Custom install_scripts command class for setup()
class install_scripts_quoted_shebang(install_scripts):
    """Ensure there are quotes around shebang paths with spaces."""
    def write_script(self, script_name, contents, mode="t", *ignored):
        shebang = str(contents.splitlines()[0])
        if shebang.startswith('#!') and ' ' in shebang[2:].strip() \
          and '"' not in shebang:
            quoted_shebang = '#!"%s"' % shebang[2:].strip()
            contents = contents.replace(shebang, quoted_shebang)
        super().write_script(script_name, contents, mode, *ignored)

# The custom install needs to be used on Windows machines
if os.name == 'nt':
    cmdclass = {'install': xinstall, 'sdist': xsdist, 'install_scripts': install_scripts_quoted_shebang}
else:
    cmdclass = {'install': xinstall, 'sdist': xsdist}


if HAVE_SETUPTOOLS:
    class xdevelop(develop):
        """Xonsh specialization of setuptools develop class."""
        def run(self):
            clean_tables()
            build_tables()
            dirty = dirty_version()
            develop.run(self)
            if dirty:
                restore_version()


def main():
    """The main entry point."""
    if sys.version_info[:2] < (3, 4):
        sys.exit('xonsh currently requires Python 3.4+')
    try:
        if '--name' not in sys.argv:
            logo_fname = os.path.join(os.path.dirname(__file__), 'logo.txt')
            with open(logo_fname, 'rb') as f:
                logo = f.read().decode('utf-8')
            print(logo)
    except UnicodeEncodeError:
        pass
    with open(os.path.join(os.path.dirname(__file__), 'README.rst'), 'r') as f:
        readme = f.read()
    scripts = ['scripts/xon.sh']
    if sys.platform == 'win32':
        scripts.append('scripts/xonsh.bat')
    else:
        scripts.append('scripts/xonsh')
    skw = dict(
        name='xonsh',
        description='A general purpose, Python-ish shell',
        long_description=readme,
        license='BSD',
        version=XONSH_VERSION,
        author='Anthony Scopatz',
        maintainer='Anthony Scopatz',
        author_email='scopatz@gmail.com',
        url='https://github.com/xonsh/xonsh',
        platforms='Cross Platform',
        classifiers=['Programming Language :: Python :: 3'],
        packages=['xonsh', 'xonsh.ply', 'xonsh.ptk', 'xonsh.parsers',
                  'xonsh.xoreutils', 'xontrib', 'xonsh.completers'],
        package_dir={'xonsh': 'xonsh', 'xontrib': 'xontrib'},
        package_data={'xonsh': ['*.json', '*.githash'], 'xontrib': ['*.xsh']},
        cmdclass=cmdclass,
        scripts=scripts,
        )
    if HAVE_SETUPTOOLS:
        # WARNING!!! Do not use setuptools 'console_scripts'
        # It validates the depenendcies (of which we have none) everytime the
        # 'xonsh' command is run. This validation adds ~0.2 sec. to the startup
        # time of xonsh - for every single xonsh run.  This prevents us from
        # reaching the goal of a startup time of < 0.1 sec.  So never ever write
        # the following:
        #
        #     'console_scripts': ['xonsh = xonsh.main:main'],
        #
        # END WARNING
        skw['entry_points'] = {
            'pygments.lexers': ['xonsh = xonsh.pyghooks:XonshLexer',
                                'xonshcon = xonsh.pyghooks:XonshConsoleLexer'],
            }
        skw['cmdclass']['develop'] = xdevelop
    setup(**skw)


if __name__ == '__main__':
    main()
