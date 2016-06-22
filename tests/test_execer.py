# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast

from xonsh.execer import Execer
from xonsh.tools import ON_WINDOWS

from tools import (mock_xonsh_env, execer_setup, check_exec, check_eval,
    check_parse)

import pytest

def setup_module():
    execer_setup()


@pytest.mark.skipif(not ON_WINDOWS, reason='Windows only stuff')
def test_win_ipconfig():
    check_eval(os.environ['SYSTEMROOT'] + '\\System32\\ipconfig.exe /all')

@pytest.mark.skipif(not ON_WINDOWS, reason='Windows only bin')
def test_ipconfig():
    check_eval('ipconfig /all')

@pytest.mark.skipif(ON_WINDOWS, reason='dont expect ls on windows')
def test_bin_ls():
    check_eval('/bin/ls -l')

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

def test_lookup_alias():
    code = (
        'def foo(a,  s=None):\n'
        '    return "bar"\n'
        '@(foo)\n')
    yield check_parse, code

def test_lookup_anon_alias():
    code = ('echo "hi" | @(lambda a, s=None: a[0]) foo bar baz\n')
    yield check_parse, code

def test_simple_func_broken():
    code = ('def prompt():\n'
            "    return '{user}'.format(\n"
            "       user='me')\n")
    yield check_parse, code

def test_bad_indent():
    code = ('if True:\n'
            'x = 1\n')
    with pytest.raises(SyntaxError):
        check_parse(code)

def test_good_rhs_subproc():
    # nonsense but parsebale
    code = 'str().split() | ![grep exit]\n'
    check_parse(code)

def test_bad_rhs_subproc():
    # nonsense but unparsebale
    code = 'str().split() | grep exit\n'
    with pytest.raises(SyntaxError):
        check_parse(code)

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

def test_pyeval_redirect():
    code = 'echo @("foo") > bar\n'
    yield check_parse, code

def test_echo_comma():
    code = 'echo ,\n'
    yield check_parse, code

def test_echo_comma_val():
    code = 'echo ,1\n'
    yield check_parse, code

def test_echo_comma_2val():
    code = 'echo 1,2\n'
    yield check_parse, code
