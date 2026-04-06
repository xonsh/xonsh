"""Tests that non-interactive modes don't eagerly import heavy modules."""

import subprocess
import sys

import pytest


def _get_loaded_modules(xonsh_args):
    """Run xonsh with given args and return set of loaded module names."""
    code = "import sys; print('\\n'.join(sorted(sys.modules)))"
    result = subprocess.run(
        [sys.executable, "-m", "xonsh", "--no-rc", *xonsh_args, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return set(result.stdout.strip().splitlines())


def test_no_history_in_command_mode():
    """xonsh -c must not import history backends."""
    modules = _get_loaded_modules([])
    history_modules = {m for m in modules if "xonsh.history" in m} - {
        "xonsh.history",
        "xonsh.history.base",
        "xonsh.history.dummy",
    }
    assert history_modules == set(), (
        f"Heavy history modules loaded in -c mode: {history_modules}"
    )


def test_no_inspectors_in_command_mode():
    """xonsh -c must not import xonsh.lib.inspectors (only needed for ?/??)."""
    modules = _get_loaded_modules([])
    assert "xonsh.lib.inspectors" not in modules, (
        "xonsh -c must not import xonsh.lib.inspectors (only needed for ?/??)"
    )
