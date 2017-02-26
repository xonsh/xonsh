# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function
from contextlib import contextmanager

import builtins
import os.path
import sys
from unittest.mock import Mock
from argparse import Namespace

import xonsh.main
import pytest
from tools import TEST_DIR


class Shell:
    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def shell(xonsh_builtins, xonsh_execer, monkeypatch):
    """Xonsh Shell Mock"""
    monkeypatch.setattr(xonsh.main, 'Shell', Shell)
    return Shell


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


@pytest.mark.parametrize(
    'arg', ['', '-i', '-vERSION', '-hAALP', 'TTTT', '-TT', '--TTT'])
def test_premain_with_file_argument(arg, shell):
    xonsh.main.premain(['tests/sample.xsh', arg])
    assert not (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


def test_premain_interactive__with_file_argument(shell):
    xonsh.main.premain(['-i', 'tests/sample.xsh'])
    assert (builtins.__xonsh_env__.get('XONSH_INTERACTIVE'))


@pytest.mark.parametrize('case', ['----', '--hep', '-TT', '--TTTT'])
def test_premain_invalid_arguments(shell, case, capsys):
    with pytest.raises(SystemExit):
        xonsh.main.premain([case])
    assert 'unrecognized argument' in capsys.readouterr()[1]


def test_xonsh_failback(shell, monkeypatch):
    failback_checker = []
    monkeypatch.setattr(sys, 'stderr', open(os.devnull, 'w'))

    def mocked_main(*args):
        raise Exception('A fake failure')
    monkeypatch.setattr(xonsh.main, 'main_xonsh', mocked_main)

    def mocked_execlp(f, *args):
        failback_checker.append(f)
        failback_checker.append(args[0])
    monkeypatch.setattr(os, 'execlp', mocked_execlp)
    monkeypatch.setattr(os.path, 'exists', lambda x: True)
    monkeypatch.setattr(sys, 'argv', ['xonsh', '-i'])

    @contextmanager
    def mocked_open(*args):
        yield ['/usr/bin/xonsh', '/usr/bin/screen', 'bash', '/bin/xshell']
    monkeypatch.setattr(builtins, 'open', mocked_open)

    xonsh.main.main()
    assert failback_checker == ['/bin/xshell', '/bin/xshell']


def test_xonsh_failback_single(shell, monkeypatch):
    class FakeFailureError(Exception):
        pass

    def mocked_main(*args):
        raise FakeFailureError()
    monkeypatch.setattr(xonsh.main, 'main_xonsh', mocked_main)
    monkeypatch.setattr(sys, 'argv', ['xonsh', '-c', 'echo', 'foo'])
    monkeypatch.setattr(sys, 'stderr', open(os.devnull, 'w'))

    with pytest.raises(FakeFailureError):
        xonsh.main.main()


def test_xonsh_failback_script_from_file(shell, monkeypatch):
    checker = []
    def mocked_execlp(f, *args):
        checker.append(f)
    monkeypatch.setattr(os, 'execlp', mocked_execlp)

    script = os.path.join(TEST_DIR, 'scripts', 'raise.xsh')
    monkeypatch.setattr(sys, 'argv', ['xonsh', script])
    monkeypatch.setattr(sys, 'stderr', open(os.devnull, 'w'))
    with pytest.raises(Exception):
        xonsh.main.main()
    assert len(checker) == 0


def test_main_xonsh_interactive_command(xonsh_builtins):
    shell_mock = Mock()
    run_code_with_cache_mock = Mock()
    cmdloop_mock = Mock()
    xonsh.main.run_code_with_cache = run_code_with_cache_mock
    shell = xonsh_builtins.__xonsh_shell__ = shell_mock()
    shell.shell.cmdloop = cmdloop_mock
    env = xonsh_builtins.__xonsh_env__
    env['LOADED_CONFIG'] = True
    args = Namespace(mode=xonsh.main.XonshMode.single_command,
                     force_interactive=True,
                     command='a=10')

    xonsh.main.main_xonsh(args)


    assert run_code_with_cache_mock.called
    assert shell.shell.cmdloop.called


def test_main_xonsh_interactive_script(xonsh_builtins, monkeypatch):
    shell_mock = Mock()
    run_script_with_cache_mock = Mock()
    isfile_mock = Mock(return_value=True)
    cmdloop_mock = Mock()
    xonsh.main.run_script_with_cache = run_script_with_cache_mock
    shell = xonsh_builtins.__xonsh_shell__ = shell_mock()
    shell.shell.cmdloop = cmdloop_mock
    env = xonsh_builtins.__xonsh_env__
    env['LOADED_CONFIG'] = True
    monkeypatch.setattr(os.path, 'isfile', isfile_mock)
    args = Namespace(mode=xonsh.main.XonshMode.script_from_file,
                     force_interactive=True,
                     file='',
                     args=[]
                     )

    xonsh.main.main_xonsh(args)


    assert run_script_with_cache_mock.called
    assert shell.shell.cmdloop.called


@pytest.mark.parametrize('args', [
    ['-ic', '"a=10"'],
    ['-i', 'script.xsh']
    ])
def test_premain_force_interactive_with_command_or_sript(args):
    args = xonsh.main.premain(args)

    assert args.mode == xonsh.main.XonshMode.interactive

