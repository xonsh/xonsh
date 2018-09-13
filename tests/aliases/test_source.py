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

    monkeypatch.setattr(builtins, "open", mocked_open)


def test_source_current_dir(mockopen, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())

    monkeypatch.setattr(builtins, "execx", mocked_execx)
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    source_alias(["foo", "bar"])
    assert checker == ["foo", "bar"]


def test_source_path(mockopen, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())

    monkeypatch.setattr(builtins, "execx", mocked_execx)
    source_alias(["foo", "bar"])
    path_foo = os.path.join("tests", "bin", "foo")
    path_bar = os.path.join("tests", "bin", "bar")
    assert checker[0].endswith(path_foo)
    assert checker[1].endswith(path_bar)
