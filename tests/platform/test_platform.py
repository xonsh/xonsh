import builtins
from unittest.mock import mock_open

import xonsh.platform as xp


def test_githash_value_error(monkeypatch):
    mocked_open = mock_open(read_data="abc123")
    monkeypatch.setattr(builtins, "open", mocked_open)

    xp.githash.cache_clear()  # githash has lru_cache
    sha, date_ = xp.githash()
    assert date_ is None
    assert sha is None


def test_pathsplit_empty_path():
    assert xp.pathsplit("") == ("", "")
