"""Bare ``${expr}`` subprocess arguments use the same detype as ``$NAME``.

Regression coverage for https://github.com/xonsh/xonsh/issues/6611.
"""

import os

import pytest

from xonsh.tools import unthreadable


def _capture_alias(xonsh_session):
    seen = []

    @unthreadable
    def _print_args(args):
        seen.append(list(args))

    xonsh_session.aliases["print_args"] = _print_args
    return seen


def test_subproc_env_expr_int_is_one_string_arg(xonsh_session):
    """``echo ${'A'}`` must stringify an int the same way ``echo $A`` does."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("$A = 2 + 2\nprint_args ${'A'}\n")
    assert seen == [["4"]]


def test_subproc_env_expr_list_is_one_string_arg(xonsh_session):
    """A list env value must stay one argument, not be flattened."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("$B = ['x', 'y']\nprint_args ${'B'}\n")
    assert seen == [["['x', 'y']"]]


def test_subproc_env_expr_matches_dollar_name(xonsh_session):
    """Bare ``${expr}`` and ``$NAME`` produce the same subprocess arguments."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec(
        "$A = 2 + 2\n"
        "$B = ['x', 'y']\n"
        "print_args $A\n"
        "print_args ${'A'}\n"
        "print_args $B\n"
        "print_args ${'B'}\n"
    )
    assert seen == [["4"], ["4"], ["['x', 'y']"], ["['x', 'y']"]]


def test_subproc_env_expr_uses_registered_detyper(xonsh_session):
    """Registered types use their detyper, not ``str()`` of the Python value."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.env["EXPAND_ENV_VARS"] = True
    xonsh_session.execer.exec(
        "print_args $EXPAND_ENV_VARS\nprint_args ${'EXPAND_ENV_VARS'}\n"
    )
    assert seen == [["1"], ["1"]]


def test_subproc_env_expr_path_detyper_is_one_arg(xonsh_session):
    """``$PATH`` detypes to one ``os.pathsep``-joined argument."""
    seen = _capture_alias(xonsh_session)
    joined = os.pathsep.join(map(str, xonsh_session.env["PATH"]))
    xonsh_session.execer.exec("print_args $PATH\nprint_args ${'PATH'}\n")
    assert seen == [[joined], [joined]]


def test_subproc_env_expr_none_is_empty_string(xonsh_session):
    """``None`` detypes to ``''`` via the default string detyper."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("$C = None\nprint_args $C\nprint_args ${'C'}\n")
    assert seen == [[""], [""]]


def test_subproc_env_expr_missing_key_is_empty_string(xonsh_session):
    """An unknown key stays the historical empty-string argument."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("print_args ${'NO_SUCH_VAR_6611'}\n")
    assert seen == [[""]]


def test_subproc_env_expr_dynamic_key(xonsh_session):
    """The expression inside ``${}`` is evaluated, then detyped."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("$A = 2 + 2\nk = 'A'\nprint_args ${k}\n")
    assert seen == [["4"]]


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("print_args $A", ["4"]),
        ('print_args "$A"', ["4"]),
        ('print_args f"{$A}"', ["4"]),
        ("print_args @($A)", ["4"]),
        ("print_args \"${'A'}\"", ["4"]),
        ("print_args @(${'A'})", ["4"]),
        ("print_args f\"{${'A'}}\"", ["4"]),
        ("print_args $B", ["['x', 'y']"]),
        ("print_args @($B)", ["x", "y"]),
        ("print_args @(${'B'})", ["x", "y"]),
    ],
)
def test_other_env_lookup_forms_unchanged(xonsh_session, cmd, expected):
    """Forms other than bare ``${expr}`` keep their existing argument shape."""
    seen = _capture_alias(xonsh_session)
    xonsh_session.execer.exec("$A = 2 + 2\n$B = ['x', 'y']\n" + cmd + "\n")
    assert seen == [expected]


def test_python_mode_env_expr_stays_raw(xonsh_session):
    """Python-mode ``${expr}`` still returns the stored object."""
    xonsh_session.execer.exec("$A = 2 + 2\n$B = ['x', 'y']\n")
    assert xonsh_session.execer.eval("${'A'}") == 4
    assert xonsh_session.execer.eval("${'B'}") == ["x", "y"]
