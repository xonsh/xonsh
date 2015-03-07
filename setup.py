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

def main():
    skw = {
        }
    setup(**skw)

if __name__ == '__main__':
    main()
