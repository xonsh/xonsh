"""Tests for pygments_cache security."""

import pytest

from xonsh.pygments_cache import load


def test_load_rejects_code_execution(tmp_path):
    """ast.literal_eval must reject arbitrary code in cache files."""
    malicious = tmp_path / "cache.py"
    malicious.write_text("__import__('os').system('echo PWNED')")
    with pytest.raises(ValueError):
        load(str(malicious))


def test_load_valid_cache(tmp_path):
    """A valid cache dict should load fine."""
    cache_file = tmp_path / "cache.py"
    cache_file.write_text("{'key': ['value1', 'value2']}")
    result = load(str(cache_file))
    assert result == {"key": ["value1", "value2"]}
