"""Smoke tests for ``xonsh.xoreutils.umask``.

Covers the pure helpers (number ↔ symbolic conversion, mask parsing) so the
tests run on any platform without poking at the running process's actual mask.

The matching ulimit tests live in ``test_xoreutils_ulimit_llm.py`` — that
module imports ``xonsh.xoreutils.ulimit`` which in turn ``import resource``
(POSIX-only), so it is skipped on Windows at collection time.
"""

import io

import pytest

from xonsh.xoreutils import umask

# --- umask helpers -----------------------------------------------------------


def test_umask_get_oct_digits_round_trip():
    digits = umask.get_oct_digits(0o644)
    assert digits == {"u": 6, "g": 4, "o": 4}
    assert umask.from_oct_digits(digits) == 0o644


@pytest.mark.parametrize("mode", [0o000, 0o022, 0o077, 0o755, 0o777])
def test_umask_oct_digits_round_trips_for_common_modes(mode):
    assert umask.from_oct_digits(umask.get_oct_digits(mode)) == mode


def test_umask_get_oct_digits_rejects_out_of_range():
    with pytest.raises(ValueError):
        umask.get_oct_digits(0o1000)
    with pytest.raises(ValueError):
        umask.get_oct_digits(-1)


def test_umask_invert_is_involutive():
    assert umask.invert(umask.invert(0o642)) == 0o642


@pytest.mark.parametrize(
    "digit,expected",
    [(0, ""), (1, "x"), (2, "w"), (4, "r"), (5, "rx"), (6, "rw"), (7, "rwx")],
)
def test_umask_get_symbolic_rep_single(digit, expected):
    assert umask.get_symbolic_rep_single(digit) == expected


def test_umask_get_symbolic_rep_full():
    assert umask.get_symbolic_rep(0o755) == "u=rwx,g=rx,o=rx"


@pytest.mark.parametrize(
    "rep,expected", [("rwx", 7), ("rw", 6), ("rx", 5), ("", 0), ("xrw", 7)]
)
def test_umask_get_numeric_rep_single(rep, expected):
    assert umask.get_numeric_rep_single(rep) == expected


@pytest.mark.parametrize(
    "arg,ok",
    [
        ("000", True),
        ("777", True),
        ("700", True),
        ("888", False),
        ("12", False),
        ("hello", False),
    ],
)
def test_umask_valid_numeric_argument(arg, ok):
    assert umask.valid_numeric_argument(arg) is ok


def test_umask_single_symbolic_arg_add():
    # starting from "rwx" (7) for owner; adding x to others
    perms = 0o770
    new_perms = umask.single_symbolic_arg("o+x", old=perms)
    assert new_perms == 0o771


def test_umask_single_symbolic_arg_remove():
    new_perms = umask.single_symbolic_arg("u-w", old=0o755)
    assert new_perms == 0o555


def test_umask_single_symbolic_arg_set_exact():
    new_perms = umask.single_symbolic_arg("a=r", old=0o000)
    assert new_perms == 0o444


def test_umask_single_symbolic_arg_invalid_mask():
    with pytest.raises(ValueError):
        umask.single_symbolic_arg("u+z", old=0o000)


def test_umask_single_symbolic_arg_unparseable():
    with pytest.raises(ValueError):
        umask.single_symbolic_arg("@@@", old=0o000)


def test_umask_help_returns_zero():
    out = io.StringIO()
    rc = umask.umask(["-h"], io.StringIO(), out, io.StringIO())
    assert rc == 0
    assert "umask" in out.getvalue().lower()


def test_umask_print_current_default_format(monkeypatch):
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    out = io.StringIO()
    rc = umask.umask([], io.StringIO(), out, io.StringIO())
    assert rc in (None, 0)
    assert out.getvalue().strip() == "022"


def test_umask_print_current_symbolic_format(monkeypatch):
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    out = io.StringIO()
    umask.umask(["-S"], io.StringIO(), out, io.StringIO())
    text = out.getvalue().strip()
    # invert(0o022) = 0o755 → u=rwx,g=rx,o=rx
    assert text == "u=rwx,g=rx,o=rx"


def test_umask_mixing_numeric_and_symbolic_errors(monkeypatch):
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    err = io.StringIO()
    rc = umask.umask(["022", "u+x"], io.StringIO(), io.StringIO(), err)
    assert rc == 1
    assert "mix numeric and symbolic" in err.getvalue()


def test_umask_too_many_numeric_args_errors(monkeypatch):
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    err = io.StringIO()
    rc = umask.umask(["022", "077"], io.StringIO(), io.StringIO(), err)
    assert rc == 1
    assert "more than one numeric argument" in err.getvalue()


def test_umask_invalid_symbolic_argument_errors(monkeypatch):
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    monkeypatch.setattr(umask.os, "umask", lambda v: 0)
    err = io.StringIO()
    rc = umask.umask(["@@@"], io.StringIO(), io.StringIO(), err)
    assert rc == 1
    assert "could not parse" in err.getvalue()


def test_umask_set_numeric_calls_os_umask(monkeypatch):
    captured = []
    monkeypatch.setattr(umask, "current_mask", lambda: 0o022)
    monkeypatch.setattr(umask.os, "umask", lambda v: captured.append(v) or 0)
    umask.umask(["077"], io.StringIO(), io.StringIO(), io.StringIO())
    assert captured == [0o077]
