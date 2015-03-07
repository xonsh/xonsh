"""The xonsh installer."""
import os
import sys
import os, sys
try:
    from setuptools import setup
    HAVE_SETUPTOOLS = True
except ImportError:
    from distutils.core import setup
    HAVE_SETUPTOOLS = False

VERSION = '0.1'

def main():
    with open('readme.rst', 'r') as f:
        readme = f.read()
    skw = dict(
        name='xonsh',
        description='an exotic, usable shell',
        long_description=readme,
        license='BSD',
        version=VERSION,
        author='Anthony Scopatz',
        maintainer='Anthony Scopatz',
        author_email='scopatz@gmail.com',
        url='https://github.com/scopatz/xonsh',
        platforms='Cross Platform',
        classifiers = ['Programming Language :: Python :: 3'],
        packages=['xonsh'],
        )
    setup(**skw)

if __name__ == '__main__':
    main()
