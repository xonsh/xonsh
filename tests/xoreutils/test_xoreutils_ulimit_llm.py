"""Smoke tests for ``xonsh.xoreutils.ulimit``.

The module imports CPython's POSIX-only ``resource`` library at import
time, so the entire file is skipped on Windows at collection time via the
``pytestmark`` short-circuit below.
"""

import io
import sys

import pytest

from xonsh.platform import ON_WINDOWS

pytestmark = pytest.mark.skipif(
    ON_WINDOWS, reason="ulimit (and the underlying `resource` module) is POSIX-only"
)

# Defer the import until after the platform skip so collection on Windows
# never tries to resolve `import resource`.
if not ON_WINDOWS:
    from xonsh.xoreutils import ulimit


# --- ulimit -----------------------------------------------------------------


def test_ulimit_help_short_circuit_succeeds():
    """`ulimit -h` and `ulimit --help` both short-circuit to print usage."""
    rc, actions = ulimit._ul_parse_args(["-h"], io.StringIO())
    assert rc is True
    assert actions == []
    rc2, actions2 = ulimit._ul_parse_args(["--help"], io.StringIO())
    assert rc2 is True
    assert actions2 == []


def test_ulimit_default_to_file_size():
    """No args: ulimit defaults to the file-size action (-f)."""
    rc, actions = ulimit._ul_parse_args([], io.StringIO())
    assert rc is True
    assert len(actions) == 1
    fn, kwargs = actions[0]
    assert fn is ulimit._ul_show
    assert kwargs["opt"] == "f"


def test_ulimit_unknown_option():
    err = io.StringIO()
    rc, actions = ulimit._ul_parse_args(["-Z"], err)
    assert rc is False
    assert actions == []
    assert "Invalid option" in err.getvalue()


def test_ulimit_long_opt_data_size():
    rc, actions = ulimit._ul_parse_args(["--data-size"], io.StringIO())
    if not rc:
        pytest.skip("RLIMIT_DATA not supported on this platform")
    assert rc is True
    assert actions[0][1]["opt"] == "d"


def test_ulimit_set_action_changes_show_to_set():
    rc, actions = ulimit._ul_parse_args(["-n", "1024"], io.StringIO())
    if not rc:
        pytest.skip("RLIMIT_NOFILE not supported on this platform")
    assert actions[-1][0] is ulimit._ul_set
    assert actions[-1][1]["soft"] == 1024


def test_ulimit_unlimited_keyword():
    rc, actions = ulimit._ul_parse_args(["-n", "unlimited"], io.StringIO())
    if not rc:
        pytest.skip("RLIMIT_NOFILE not supported on this platform")
    assert actions[-1][0] is ulimit._ul_set
    assert actions[-1][1]["soft"] == "unlimited"


def test_ulimit_show_runs(capfd):
    """`ulimit` (no args) prints something on stdout and returns 0."""
    rc = ulimit.ulimit([], sys.stdin, sys.stdout, sys.stderr)
    out, _ = capfd.readouterr()
    assert rc == 0
    # there's at least one line of output (the file-size limit)
    assert out.strip() != ""


def test_ulimit_help_prints_usage(capfd):
    rc = ulimit.ulimit(["-h"], sys.stdin, sys.stdout, sys.stderr)
    out, _ = capfd.readouterr()
    assert rc == 0
    assert "Usage: ulimit" in out
