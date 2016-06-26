# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function

import builtins
from unittest.mock import patch
import xonsh.main

from tools import mock_xonsh_env



def Shell(*args, **kwargs):
    pass


def test_premain():
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        with patch('sys.stdin.isatty') as faketty:
            faketty.return_value = True
            xonsh.main.premain([])
            assert builtins.__xonsh_env__.get('XONSH_LOGIN')

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-i'])
        assert (builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-i'])
        assert (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-l', '-c', 'echo "hi"'])
        assert (builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-c', 'echo "hi"'])
        assert not (builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-l'])
        assert (builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-DTEST1=1616', '-DTEST2=LOL'])
        assert (builtins.__xonsh_env__.get('TEST1') == '1616')
        assert (builtins.__xonsh_env__.get('TEST2') == 'LOL')


def test_premain_with_file_argument():
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['tests/sample.xsh'])
        assert not (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))

    for case in ('-i', '-vERSION', '-hAALP','TTTT', '-TT', '--TTT'):
        with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
            xonsh.main.premain(['tests/sample.xsh', case])
            assert not (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))

    # interactive
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-i', 'tests/sample.xsh'])
        assert (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))



def test_premain_invalid_arguments():
    # pytest transition
    # TODO: check for proper error msg in stdout (howto nose?)
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        for case in ('----', '--hep', '-TT', '--TTTT'):
            try:
                xonsh.main.premain([case])
            except SystemExit:
                pass
            else:
                assert False
