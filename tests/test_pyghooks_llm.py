"""Tests for bg validation in pyghooks — _run_bg_validation must always
populate _cmd_valid_cache, even when the generation token is stale."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_bg_validation_globals():
    """Reset module-level bg-validation state before each test."""
    from xonsh import pyghooks as ph

    ph._cmd_valid_cache.clear()
    ph._pending_cmds.clear()
    ph._validation_gen = 0
    ph._ptk_app = None
    yield
    ph._cmd_valid_cache.clear()
    ph._pending_cmds.clear()
    ph._validation_gen = 0
    ph._ptk_app = None


def test_stale_gen_still_caches():
    from xonsh import pyghooks as ph

    # Simulate: a command was scheduled at gen=1, but by the time
    # the bg thread runs, gen has moved to 5 (new keystrokes).
    ph._pending_cmds.add("python3")
    ph._validation_gen = 5

    stale_gen = 1

    with patch.object(ph, "locate_executable", return_value="/usr/bin/python3"):
        ph._run_bg_validation(stale_gen)

    # Result MUST be in cache despite stale gen
    assert "python3" in ph._cmd_valid_cache
    assert ph._cmd_valid_cache["python3"] is True


def test_stale_gen_skips_invalidation():
    from xonsh import pyghooks as ph

    mock_app = MagicMock()
    ph._ptk_app = mock_app
    ph._pending_cmds.add("git")
    ph._validation_gen = 5

    stale_gen = 1

    with patch.object(ph, "locate_executable", return_value="/usr/bin/git"):
        ph._run_bg_validation(stale_gen)

    assert ph._cmd_valid_cache["git"] is True
    # invalidate() must NOT be called — gen is stale
    mock_app.invalidate.assert_not_called()


def test_current_gen_caches_and_invalidates():
    from xonsh import pyghooks as ph

    mock_app = MagicMock()
    mock_app.layout.find_all_controls.return_value = []
    ph._ptk_app = mock_app
    ph._pending_cmds.add("ls")
    ph._validation_gen = 3

    current_gen = 3

    with patch.object(ph, "locate_executable", return_value="/bin/ls"):
        ph._run_bg_validation(current_gen)

    assert ph._cmd_valid_cache["ls"] is True
    mock_app.invalidate.assert_called_once()
