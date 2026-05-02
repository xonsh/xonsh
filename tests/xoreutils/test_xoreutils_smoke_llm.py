"""Smoke tests for the small ``xonsh.xoreutils`` commands.

Covers ``echo``, ``pwd``, ``tee``, ``tty``, ``yes`` — the trivial cross-platform
coreutils. Tests follow the ``args, stdin, stdout, stderr`` callable-alias
contract: every command is a plain function called with explicit streams.
"""

import io
import os

import pytest

from xonsh.xoreutils import echo, pwd, tee, tty, yes


# --- echo -------------------------------------------------------------------


def _run_echo(args):
    out = io.StringIO()
    err = io.StringIO()
    rc = echo.echo(list(args), io.StringIO(), out, err)
    return rc, out.getvalue(), err.getvalue()


def test_echo_simple_string():
    _, stdout, _ = _run_echo(["hello"])
    assert stdout == "hello\n"


def test_echo_multiple_args_joined_with_space():
    _, stdout, _ = _run_echo(["foo", "bar", "baz"])
    assert stdout == "foo bar baz\n"


def test_echo_no_newline_with_dash_n():
    _, stdout, _ = _run_echo(["-n", "no-newline"])
    assert stdout == "no-newline"


def test_echo_help_returns_zero():
    rc, stdout, _ = _run_echo(["--help"])
    assert rc == 0
    assert "echo" in stdout.lower()


def test_echo_help_short_flag():
    rc, stdout, _ = _run_echo(["-h"])
    assert rc == 0
    assert echo.ECHO_HELP in stdout


def test_echo_escapes_with_dash_e():
    _, stdout, _ = _run_echo(["-e", "a\\tb"])
    assert stdout == "a\tb\n"


def test_echo_dash_capital_e_disables_escapes():
    _, stdout, _ = _run_echo(["-E", "a\\tb"])
    assert stdout == "a\\tb\n"


def test_echo_empty_args_prints_blank_line():
    _, stdout, _ = _run_echo([])
    assert stdout == "\n"


def test_echo_parse_args_defaults():
    out = echo._echo_parse_args(["hello"])
    assert out == {"escapes": False, "end": "\n", "help": False}


def test_echo_parse_args_combined_flags():
    out = echo._echo_parse_args(["-e", "-n", "hi"])
    assert out["escapes"] is True
    assert out["end"] == ""
    assert out["help"] is False


# --- pwd --------------------------------------------------------------------


def test_pwd_prints_current_dir(xession, tmp_path):
    xession.env["PWD"] = str(tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    rc = pwd.pwd([], io.StringIO(), out, err)
    assert rc == 0
    assert out.getvalue().strip() == str(tmp_path)


def test_pwd_help_returns_zero(xession, tmp_path):
    xession.env["PWD"] = str(tmp_path)
    out = io.StringIO()
    rc = pwd.pwd(["--help"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert "pwd" in out.getvalue().lower()


def test_pwd_short_help_flag(xession, tmp_path):
    xession.env["PWD"] = str(tmp_path)
    out = io.StringIO()
    rc = pwd.pwd(["-h"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert pwd.PWD_HELP in out.getvalue()


def test_pwd_physical_resolves_symlinks(xession, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(str(real), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")
    xession.env["PWD"] = str(link)
    out = io.StringIO()
    rc = pwd.pwd(["-P"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    # the printed path should not be the symlink itself
    assert out.getvalue().strip() == os.path.realpath(str(link))


# --- tee --------------------------------------------------------------------


def test_tee_writes_to_stdout_and_file(tmp_path):
    target = tmp_path / "tee.out"
    stdin = io.StringIO("hello tee")
    stdout = io.StringIO()
    rc = tee.tee([str(target)], stdin, stdout, io.StringIO())
    assert rc == 0
    assert stdout.getvalue() == "hello tee"
    assert target.read_text() == "hello tee"


def test_tee_append_mode(tmp_path):
    target = tmp_path / "tee.out"
    target.write_text("existing\n")
    stdin = io.StringIO("appended")
    stdout = io.StringIO()
    rc = tee.tee(["-a", str(target)], stdin, stdout, io.StringIO())
    assert rc == 0
    assert target.read_text() == "existing\nappended"


def test_tee_long_append_flag(tmp_path):
    target = tmp_path / "tee.out"
    target.write_text("a")
    stdin = io.StringIO("b")
    rc = tee.tee(["--append", str(target)], stdin, io.StringIO(), io.StringIO())
    assert rc == 0
    assert target.read_text() == "ab"


def test_tee_no_stdin_returns_one():
    out = io.StringIO()
    err = io.StringIO()
    rc = tee.tee([], None, out, err)
    assert rc == 1
    assert "stdin" in err.getvalue()


def test_tee_help_returns_zero():
    out = io.StringIO()
    rc = tee.tee(["--help"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert "tee" in out.getvalue().lower()


def test_tee_dash_writes_to_stdout_only():
    """A FILE of '-' aliases stdout."""
    stdin = io.StringIO("dash")
    stdout = io.StringIO()
    rc = tee.tee(["-"], stdin, stdout, io.StringIO())
    assert rc == 0
    # '-' is appended as stdout once + stdout is appended again at the end,
    # so content gets written twice into the same buffer.
    assert "dash" in stdout.getvalue()


# --- tty --------------------------------------------------------------------


def test_tty_help_returns_zero():
    out = io.StringIO()
    rc = tty.tty(["--help"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert "tty" in out.getvalue().lower()


def test_tty_not_a_tty_for_regular_file(tmp_path):
    """A regular file has a fileno but isn't a tty, so tty returns 1."""
    p = tmp_path / "stdin"
    p.write_text("")
    out = io.StringIO()
    with open(p) as f:
        rc = tty.tty([], f, out, io.StringIO())
    assert rc == 1
    assert "not a tty" in out.getvalue()


def test_tty_silent_no_output(tmp_path):
    """The -s flag suppresses output but keeps the exit status."""
    p = tmp_path / "stdin"
    p.write_text("")
    out = io.StringIO()
    with open(p) as f:
        rc = tty.tty(["-s"], f, out, io.StringIO())
    assert rc == 1
    assert out.getvalue() == ""


def test_tty_invalid_option_returns_two():
    err = io.StringIO()
    rc = tty.tty(["--bogus"], io.StringIO(), io.StringIO(), err)
    assert rc == 2
    assert "Invalid option" in err.getvalue()


# --- yes --------------------------------------------------------------------


def test_yes_help_returns_zero():
    out = io.StringIO()
    rc = yes.yes(["--help"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert "yes" in out.getvalue().lower()


class _LimitedStringIO(io.StringIO):
    """Raises KeyboardInterrupt after writing ``limit`` bytes."""

    def __init__(self, limit):
        super().__init__()
        self._limit = limit

    def write(self, data):
        n = super().write(data)
        if self.tell() >= self._limit:
            raise KeyboardInterrupt()
        return n


def test_yes_default_repeats_y():
    """yes with no args should print 'y\\n' until interrupted, returning 130."""
    buf = _LimitedStringIO(20)
    rc = yes.yes([], io.StringIO(), buf, io.StringIO())
    assert rc == 130
    out = buf.getvalue()
    # every line is a bare 'y'
    for line in out.splitlines():
        assert line == "y"
    assert out.count("y") >= 10


def test_yes_with_custom_string():
    buf = _LimitedStringIO(200)
    rc = yes.yes(["hello", "world"], io.StringIO(), buf, io.StringIO())
    assert rc == 130
    # Iterating multiple lines: each *complete* line (every line except
    # possibly the last truncated one) must equal "hello world".
    lines = buf.getvalue().splitlines()
    complete = lines[:-1] if buf.getvalue() and not buf.getvalue().endswith("\n") else lines
    assert complete  # at least one complete line was written
    for line in complete:
        assert line == "hello world"
