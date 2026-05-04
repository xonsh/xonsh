"""Tests for ``xonsh format`` CLI behaviour.

Mirrors Black's CLI conventions: in-place by default, ``--check`` for
non-zero exit on would-be reformat, ``--diff`` for unified-diff output,
``-`` for stdin/stdout streaming.
"""

from __future__ import annotations

import io
import sys

import pytest

from xonsh.formatter import cli as fcli


def _run(argv, capsys, monkeypatch, stdin_text=None):
    """Invoke the formatter CLI and capture stdout/stderr/exit."""
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    rc = fcli.main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ---------------------------------------------------------------------
# In-place writes
# ---------------------------------------------------------------------


def test_in_place_rewrites_file(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x=1\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == fcli.EXIT_OK
    assert f.read_text() == "x = 1\n"
    assert "reformatted" in err


def test_in_place_unchanged_file(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == fcli.EXIT_OK
    assert "unchanged" in err


def test_quiet_suppresses_status(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x=1\n")
    rc, out, err = _run([str(f), "-q"], capsys, monkeypatch)
    assert rc == fcli.EXIT_OK
    assert err == ""


# ---------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------


def test_check_flags_changes_with_exit_one(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x=1\n")
    rc, out, err = _run([str(f), "--check"], capsys, monkeypatch)
    assert rc == fcli.EXIT_CHANGED
    # File must NOT be modified by --check.
    assert f.read_text() == "x=1\n"
    assert "would reformat" in err


def test_check_clean_file_exits_zero(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    rc, out, err = _run([str(f), "--check"], capsys, monkeypatch)
    assert rc == fcli.EXIT_OK


# ---------------------------------------------------------------------
# --diff
# ---------------------------------------------------------------------


def test_diff_emits_unified_diff(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x=1\n")
    rc, out, err = _run([str(f), "--diff"], capsys, monkeypatch)
    assert rc == fcli.EXIT_CHANGED
    # File must NOT be modified by --diff.
    assert f.read_text() == "x=1\n"
    assert "-x=1" in out
    assert "+x = 1" in out


# ---------------------------------------------------------------------
# Stdin via "-"
# ---------------------------------------------------------------------


def test_stdin_dash_writes_to_stdout(capsys, monkeypatch):
    rc, out, err = _run(["-"], capsys, monkeypatch, stdin_text="x=1\n")
    assert rc == fcli.EXIT_OK
    assert out == "x = 1\n"


def test_stdin_dash_check_mode(capsys, monkeypatch):
    rc, out, err = _run(["-", "--check"], capsys, monkeypatch, stdin_text="x=1\n")
    assert rc == fcli.EXIT_CHANGED


def test_stdin_dash_check_clean(capsys, monkeypatch):
    rc, out, err = _run(["-", "--check"], capsys, monkeypatch, stdin_text="x = 1\n")
    assert rc == fcli.EXIT_OK


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


def test_missing_file_exits_with_error_code(tmp_path, capsys, monkeypatch):
    rc, out, err = _run([str(tmp_path / "does_not_exist.xsh")], capsys, monkeypatch)
    assert rc == fcli.EXIT_ERROR
    assert "error" in err


def test_unparseable_file_exits_with_error_code(tmp_path, capsys, monkeypatch):
    f = tmp_path / "bad.xsh"
    # EOF inside an open paren — the tokenizer raises TokenError,
    # which the formatter wraps as FormatError.
    f.write_text("x = (1 + \n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == fcli.EXIT_ERROR
    # File must NOT be modified when tokenization fails.
    assert f.read_text() == "x = (1 + \n"


# ---------------------------------------------------------------------
# Multi-file handling
# ---------------------------------------------------------------------


def test_multiple_files_one_dirty(tmp_path, capsys, monkeypatch):
    a = tmp_path / "a.xsh"
    b = tmp_path / "b.xsh"
    a.write_text("x = 1\n")  # clean
    b.write_text("y=2\n")  # dirty
    rc, out, err = _run([str(a), str(b), "--check"], capsys, monkeypatch)
    assert rc == fcli.EXIT_CHANGED
    assert a.read_text() == "x = 1\n"
    assert b.read_text() == "y=2\n"


def test_multiple_files_in_place_writes_dirty(tmp_path, capsys, monkeypatch):
    a = tmp_path / "a.xsh"
    b = tmp_path / "b.xsh"
    a.write_text("x = 1\n")
    b.write_text("y=2\n")
    rc, out, err = _run([str(a), str(b)], capsys, monkeypatch)
    assert rc == fcli.EXIT_OK
    assert a.read_text() == "x = 1\n"
    assert b.read_text() == "y = 2\n"


# ---------------------------------------------------------------------
# argparse help / no-files behaviour
# ---------------------------------------------------------------------


def test_no_files_errors():
    """argparse must reject an empty argument list."""
    with pytest.raises(SystemExit):
        fcli.main([])
