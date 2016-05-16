# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast

from nose.tools import assert_raises

from xonsh.execer import Execer
from xonsh.tools import ON_WINDOWS

from tools import mock_xonsh_env

DEBUG_LEVEL = 0
EXECER = None

#
# Helpers
#

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

def check_eval(input):
    with mock_xonsh_env({'AUTO_CD': False, 'XONSH_ENCODING' :'utf-8',
                         'XONSH_ENCODING_ERRORS': 'strict', 'PATH': []}):
        EXECER.debug_level = DEBUG_LEVEL
        EXECER.eval(input)

def check_parse(input):
    with mock_xonsh_env(None):
        EXECER.debug_level = DEBUG_LEVEL
        EXECER.parse(input, ctx=None)

#
# Tests
#

if ON_WINDOWS:
    def test_win_ipconfig():
        yield (check_eval,
               os.environ['SYSTEMROOT'] + '\\System32\\ipconfig.exe /all')

    def test_ipconfig():
        yield check_eval, 'ipconfig /all'

else:
    def test_bin_ls():
        yield check_eval, '/bin/ls -l'

def test_ls_dashl():
    yield check_parse, 'ls -l'

def test_which_ls():
    yield check_parse, 'which ls'

def test_echo_hello():
    yield check_parse, 'echo hello'

def test_simple_func():
    code = ('def prompt():\n'
            "    return '{user}'.format(user='me')\n")
    yield check_parse, code

def test_simple_func_broken():
    code = ('def prompt():\n'
            "    return '{user}'.format(\n"
            "       user='me')\n")
    yield check_parse, code

def test_bad_indent():
    code = ('if True:\n'
            'x = 1\n')
    assert_raises(SyntaxError, check_parse, code)

def test_indent_with_empty_line():
    code = ('if True:\n'
            '\n'
            '    some_command for_sub_process_mode\n')
    yield check_parse, code

def test_command_in_func():
    code = ('def f():\n'
            '    echo hello\n')
    yield check_parse, code

def test_command_in_func_with_comment():
    code = ('def f():\n'
            '    echo hello # comment\n')
    yield check_parse, code



if __name__ == '__main__':
    nose.runmodule()
