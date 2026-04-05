"""Tests for pygments_cache security."""

import pytest

import xonsh.pygments_cache as pc


def test_load_rejects_code_execution(tmp_path):
    """ast.literal_eval must reject arbitrary code in cache files."""
    malicious = tmp_path / "cache.py"
    malicious.write_text("__import__('os').system('echo PWNED')")
    with pytest.raises(ValueError):
        pc.load(str(malicious))


def test_load_valid_cache(tmp_path):
    """A valid cache dict should load fine."""
    cache_file = tmp_path / "cache.py"
    cache_file.write_text("{'key': ['value1', 'value2']}")
    old_cache = pc.CACHE
    try:
        result = pc.load(str(cache_file))
        assert result == {"key": ["value1", "value2"]}
    finally:
        pc.CACHE = old_cache
