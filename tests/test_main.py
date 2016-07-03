# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function

import builtins
import sys
from unittest.mock import patch

import xonsh.main

import pytest


def Shell(*args, **kwargs):
    pass


@pytest.fixture
def shell(xonsh_builtins, monkeypatch):
    """Xonsh Shell Mock"""
    monkeypatch.setattr(xonsh.main, 'Shell', Shell)


def test_premain_no_arg(shell, monkeypatch):
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    xonsh.main.premain([])
    assert builtins.__xonsh_env__.get('XONSH_LOGIN')


def test_premain_interactive(shell):
    xonsh.main.premain(['-i'])
    assert (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


def test_premain_login_command(shell):
    xonsh.main.premain(['-l', '-c', 'echo "hi"'])
    assert (builtins.__xonsh_env__.get('XONSH_LOGIN'))


def test_premain_login(shell):
    xonsh.main.premain(['-l'])
    assert (builtins.__xonsh_env__.get('XONSH_LOGIN'))


def test_premain_D(shell):
    xonsh.main.premain(['-DTEST1=1616', '-DTEST2=LOL'])
    assert (builtins.__xonsh_env__.get('TEST1') == '1616')
    assert (builtins.__xonsh_env__.get('TEST2') == 'LOL')


@pytest.mark.parametrize('arg',
    ['', '-i', '-vERSION', '-hAALP','TTTT', '-TT', '--TTT'] )
def test_premain_with_file_argument(arg, shell):
    xonsh.main.premain(['tests/sample.xsh', arg])
    assert not (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


def test_premain_interactive__with_file_argument(shell):
    xonsh.main.premain(['-i', 'tests/sample.xsh'])
    assert (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


@pytest.mark.parametrize('case', ['----', '--hep', '-TT', '--TTTT'])
def test_premain_invalid_arguments(case, shell, capsys):
    with pytest.raises(SystemExit):
        xonsh.main.premain([case])
    assert 'unrecognized argument' in capsys.readouterr()[1]
