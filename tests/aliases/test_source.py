import os.path
import pytest

import builtins
from contextlib import contextmanager
from unittest.mock import MagicMock
from xonsh.aliases import source_alias


@pytest.fixture
def mockopen(xonsh_builtins, monkeypatch):
    @contextmanager
    def mocked_open(fpath, *args, **kwargs):
        yield MagicMock(read=lambda: fpath)

    monkeypatch.setattr(builtins, "open", mocked_open)


@pytest.fixture
def mocked_execx_checker(xession, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())

    monkeypatch.setattr(xession.builtins, "execx", mocked_execx)
    return checker


def test_source_current_dir(mockopen, monkeypatch, mocked_execx_checker):
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    source_alias(["foo", "bar"])
    assert mocked_execx_checker == ["foo", "bar"]


def test_source_path(mockopen, mocked_execx_checker):
    source_alias(["foo", "bar"])
    path_foo = os.path.join("tests", "bin", "foo")
    path_bar = os.path.join("tests", "bin", "bar")
    assert mocked_execx_checker[0].endswith(path_foo)
    assert mocked_execx_checker[1].endswith(path_bar)
