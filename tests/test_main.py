# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function

import builtins
from unittest.mock import patch

import nose
from nose.tools import assert_true, assert_false

import xonsh.main

from tools import mock_xonsh_env



def Shell(*args, **kwargs):
    pass


def test_login_shell():

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain([])
        assert_true(builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-l', '-c', 'echo "hi"'])
        assert_true(builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-c', 'echo "hi"'])
        assert_false(builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-l'])
        assert_true(builtins.__xonsh_env__.get('XONSH_LOGIN'))


def test_login_shell_with_file_argument():
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['tests/sample.xsh'])
        assert_false(builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))

    for case in ('TTTT', '-TT', '--TTT'):
        with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
            xonsh.main.premain(['tests/sample.xsh', case])
            assert_false(builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


def test_login_shell_invalid_arguments():
    # pytest transition
    # TODO: check for proper error msg in stdout (howto nose?)
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        try:
            xonsh.main.premain(['----'])
            assert False
        except SystemExit:
            pass
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        try:
            xonsh.main.premain(['--hep'])
            assert False
        except SystemExit:
            pass
    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        try:
            xonsh.main.premain(['-TT'])
            assert False
        except SystemExit:
           pass


if __name__ == '__main__':
    nose.runmodule()
