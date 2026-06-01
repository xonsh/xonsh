"""Tests for ``xonsh check`` and the ``xonsh -n`` / ``--no-execute`` flag.

The checker parses + compiles xonsh source down to a code object but never
runs it (the analogue of ``bash -n`` / ``nu --no-execute``). Both the
subcommand and the flag share one engine, :func:`xonsh.checker.cli.check_source`.
"""

from __future__ import annotations

import io
import sys
import types

import pytest

from xonsh.checker import cli as ccli


def _run(argv, capsys, monkeypatch, stdin_text=None):
    """Invoke ``xonsh check`` and capture stdout/stderr/exit."""
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    rc = ccli.main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _ns(command=None, file=None):
    """Build the minimal argparse-like namespace ``check_no_execute`` reads."""
    return types.SimpleNamespace(command=command, file=file)


# ---------------------------------------------------------------------
# Engine: check_source
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "x = 1",
        "ls -l | grep foo",  # subprocess mode
        "echo @(1 + 2)",  # python substitution inside subproc
        "for i in range(3):\n    print(i)",
        "y = $(ls -l)",  # captured subproc
        "# only a comment",
        "",  # empty input compiles to pass
    ],
)
def test_check_source_accepts_valid(src):
    assert ccli.check_source(src) is None


@pytest.mark.parametrize(
    "src",
    [
        "'unclosed",
        "x = (1 +",
        "def f(:\n    pass",
        "return 5",  # compile-time error, not a parse error
    ],
)
def test_check_source_rejects_invalid(src):
    with pytest.raises(SyntaxError):
        ccli.check_source(src)


def test_check_source_does_not_execute(tmp_path):
    # A side effect in the source must NOT happen during a check.
    marker = tmp_path / "ran"
    src = f"open({str(marker)!r}, 'w').write('x')\n"
    ccli.check_source(src)
    assert not marker.exists()


# ---------------------------------------------------------------------
# Subcommand: xonsh check FILE...
# ---------------------------------------------------------------------


def test_valid_file_ok(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\nls -l | grep foo\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == ccli.EXIT_OK
    assert f"{f}: OK" in err


def test_invalid_file_reports_location(tmp_path, capsys, monkeypatch):
    f = tmp_path / "bad.xsh"
    f.write_text("x = (1 +\n")
    rc, out, err = _run([str(f)], capsys, monkeypatch)
    assert rc == ccli.EXIT_SYNTAX
    assert f"{f}:1" in err  # path:line(:col) prefix
    assert "^" in err  # caret under the offending column


def test_quiet_suppresses_ok(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    rc, out, err = _run([str(f), "-q"], capsys, monkeypatch)
    assert rc == ccli.EXIT_OK
    assert err == ""


def test_quiet_still_reports_errors(tmp_path, capsys, monkeypatch):
    f = tmp_path / "bad.xsh"
    f.write_text("x = (1 +\n")
    rc, out, err = _run([str(f), "-q"], capsys, monkeypatch)
    assert rc == ccli.EXIT_SYNTAX
    assert str(f) in err


def test_missing_file_is_read_error(tmp_path, capsys, monkeypatch):
    missing = tmp_path / "nope.xsh"
    rc, out, err = _run([str(missing)], capsys, monkeypatch)
    assert rc == ccli.EXIT_ERROR
    assert "error" in err


def test_directory_is_read_error(tmp_path, capsys, monkeypatch):
    rc, out, err = _run([str(tmp_path)], capsys, monkeypatch)
    assert rc == ccli.EXIT_ERROR


def test_multiple_files_mixed(tmp_path, capsys, monkeypatch):
    good = tmp_path / "good.xsh"
    good.write_text("x = 1\n")
    bad = tmp_path / "bad.xsh"
    bad.write_text("'unclosed\n")
    rc, out, err = _run([str(good), str(bad)], capsys, monkeypatch)
    assert rc == ccli.EXIT_SYNTAX
    assert f"{good}: OK" in err
    assert str(bad) in err


def test_read_error_takes_precedence_over_syntax(tmp_path, capsys, monkeypatch):
    bad = tmp_path / "bad.xsh"
    bad.write_text("'unclosed\n")
    missing = tmp_path / "nope.xsh"
    rc, out, err = _run([str(bad), str(missing)], capsys, monkeypatch)
    assert rc == ccli.EXIT_ERROR  # 123 wins over 1


def test_stdin_dash(capsys, monkeypatch):
    rc, out, err = _run(["-"], capsys, monkeypatch, stdin_text="x = 1\n")
    assert rc == ccli.EXIT_OK
    assert "<stdin>: OK" in err


def test_stdin_dash_invalid(capsys, monkeypatch):
    rc, out, err = _run(["-"], capsys, monkeypatch, stdin_text="x = (1 +\n")
    assert rc == ccli.EXIT_SYNTAX
    assert "<stdin>:1" in err


# ---------------------------------------------------------------------
# Flag engine: check_no_execute (xonsh -n)
# ---------------------------------------------------------------------


def test_no_execute_command_valid_is_silent(capsys):
    rc = ccli.check_no_execute(_ns(command="x = 1; print(x)"))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_OK
    assert out == "" and err == ""  # bash -n style: silent on success


def test_no_execute_command_invalid(capsys):
    rc = ccli.check_no_execute(_ns(command="x = (1 +"))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_SYNTAX
    assert "<string>:1" in err


def test_no_execute_file_valid(tmp_path, capsys):
    f = tmp_path / "a.xsh"
    f.write_text("ls -l | grep foo\n")
    rc = ccli.check_no_execute(_ns(file=str(f)))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_OK
    assert err == ""


def test_no_execute_file_invalid(tmp_path, capsys):
    f = tmp_path / "bad.xsh"
    f.write_text("def f(:\n    pass\n")
    rc = ccli.check_no_execute(_ns(file=str(f)))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_SYNTAX
    assert str(f) in err


def test_no_execute_missing_file(tmp_path, capsys):
    rc = ccli.check_no_execute(_ns(file=str(tmp_path / "nope.xsh")))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_ERROR


def test_no_execute_directory(tmp_path, capsys):
    rc = ccli.check_no_execute(_ns(file=str(tmp_path)))
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_ERROR
    assert "directory" in err.lower()


def test_no_execute_stdin(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("x = 1\n"))
    rc = ccli.check_no_execute(_ns())
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_OK


def test_no_execute_interactive_nothing_to_check(capsys, monkeypatch):
    fake = io.StringIO("")
    monkeypatch.setattr(fake, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys, "stdin", fake)
    rc = ccli.check_no_execute(_ns())
    out, err = capsys.readouterr()
    assert rc == ccli.EXIT_ERROR
    assert "nothing to check" in err


# ---------------------------------------------------------------------
# Wiring: main() dispatch and premain() -n flag
# ---------------------------------------------------------------------


def test_main_dispatches_check_subcommand(tmp_path):
    import xonsh.main

    f = tmp_path / "a.xsh"
    f.write_text("x = 1\n")
    with pytest.raises(SystemExit) as ei:
        xonsh.main.main(["check", str(f), "-q"])
    assert ei.value.code == ccli.EXIT_OK


def test_main_dispatches_check_subcommand_invalid(tmp_path):
    import xonsh.main

    f = tmp_path / "bad.xsh"
    f.write_text("x = (1 +\n")
    with pytest.raises(SystemExit) as ei:
        xonsh.main.main(["check", str(f)])
    assert ei.value.code == ccli.EXIT_SYNTAX


def test_premain_n_flag_valid():
    import xonsh.main

    with pytest.raises(SystemExit) as ei:
        xonsh.main.premain(["-n", "-c", "x = 1; print(x)"])
    assert ei.value.code == ccli.EXIT_OK


def test_premain_n_flag_invalid():
    import xonsh.main

    with pytest.raises(SystemExit) as ei:
        xonsh.main.premain(["-n", "-c", "x = (1 +"])
    assert ei.value.code == ccli.EXIT_SYNTAX
