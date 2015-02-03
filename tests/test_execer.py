"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast

from xonsh.execer import Execer

DEBUG_LEVEL = 0
EXECER = None

def setup():
    # only setup one parser
    global EXECER
    EXECER = Execer(debug_level=DEBUG_LEVEL)


def check_exec(input):
    if not input.endswith('\n'):
        input += '\n'
    EXECER.debug_level = DEBUG_LEVEL
    EXECER.exec(input)


def test_bin_ls():
    yield check_exec, '/bin/ls -l'


if __name__ == '__main__':
    nose.runmodule()
