# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function

import builtins
from unittest.mock import patch

import nose
from nose.tools import assert_true, assert_false

import xonsh.main

from tools import mock_xonsh_env


def test_login_shell():
    def Shell(*args, **kwargs):
        pass

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain([])
        assert_false(builtins.__xonsh_env__.get('XONSH_LOGIN'))

    with patch('xonsh.main.Shell', Shell), mock_xonsh_env({}):
        xonsh.main.premain(['-l'])
        assert_true(builtins.__xonsh_env__.get('XONSH_LOGIN'))

if __name__ == '__main__':
    nose.runmodule()
