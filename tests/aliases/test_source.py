import os.path
import pytest

from contextlib import contextmanager
from unittest.mock import MagicMock
from xonsh.aliases import source_alias, builtins


@pytest.fixture
def mockopen(xonsh_builtins, monkeypatch):
    @contextmanager
    def mocked_open(fpath, *args, **kwargs):
        yield MagicMock(read=lambda: fpath)
    monkeypatch.setattr(builtins, 'open', mocked_open)


def test_source_context(mockopen, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())
    monkeypatch.setattr(builtins, 'execx', mocked_execx)
    monkeypatch.setattr(os.path, 'isfile', lambda x: True)
    ctx = builtins.__xonsh_ctx__
    ctx['foo'] = 'ctx_foo'
    ctx['bar'] = 'ctx_bar'

    source_alias(['foo', 'bar'])
    assert checker[0].endswith('ctx_foo')
    assert checker[1].endswith('ctx_bar')


def test_source_current_dir(mockopen, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())
    monkeypatch.setattr(builtins, 'execx', mocked_execx)
    monkeypatch.setattr(os.path, 'isfile', lambda x: True)
    source_alias(['foo', 'bar'])
    assert checker == ['foo', 'bar']


def test_source_path(mockopen, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())
    monkeypatch.setattr(builtins, 'execx', mocked_execx)
    source_alias(['foo', 'bar'])
    assert checker[0].endswith('tests/bin/foo')
    assert checker[1].endswith('tests/bin/bar')
