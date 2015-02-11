"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast

from xonsh.execer import Execer

from tools import mock_xonsh_env

DEBUG_LEVEL = 0
EXECER = None

def setup():
    # only setup one parser
    global EXECER
    EXECER = Execer(debug_level=DEBUG_LEVEL)


def check_exec(input):
    with mock_xonsh_env(None):
        if not input.endswith('\n'):
            input += '\n'
        EXECER.debug_level = DEBUG_LEVEL
        EXECER.exec(input)

def test_bin_ls():
    yield check_exec, '/bin/ls -l'

def test_ls_dashl():
    yield check_exec, 'ls -l'

def test_which_ls():
    yield check_exec, 'which ls'


if __name__ == '__main__':
    nose.runmodule()
