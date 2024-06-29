import builtins
from contextlib import contextmanager
from unittest.mock import MagicMock

import xonsh.platform as xp


def test_githash_value_error(monkeypatch):
    @contextmanager
    def mocked_open(*args):
        yield MagicMock(read=lambda: "abc123")

    monkeypatch.setattr(builtins, "open", mocked_open)
    sha, date_ = xp.githash()
    assert date_ is None
    assert sha is None


def test_pathsplit_empty_path():
    assert xp.pathsplit("") == ("", "")
