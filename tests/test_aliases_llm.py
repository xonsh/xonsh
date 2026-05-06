"""Unit tests for ``win_sudo`` — the Windows UAC sudo fallback alias.

The function under test is platform-independent enough to exercise on any host:
``xonsh.platforms.winutils.sudo`` is mocked out so the elevation API is never
actually called. See issue #5706 for the original bug.
"""

import os

import pytest

from xonsh import aliases
from xonsh.aliases import WINDOWS_CMD_ALIASES, win_sudo


@pytest.fixture
def fake_winutils_sudo(monkeypatch):
    """Record calls to ``winutils.sudo`` instead of triggering ShellExecute."""
    import xonsh.platforms.winutils as winutils

    calls = []

    def recorder(executable, args=None):
        calls.append((executable, list(args) if args is not None else None))
        return "elevated"

    monkeypatch.setattr(winutils, "sudo", recorder)
    return calls


def test_no_args_returns_usage_error(fake_winutils_sudo):
    out, err, rc = win_sudo([])
    assert out == ""
    assert "missing executable" in err
    assert rc == 1
    assert fake_winutils_sudo == []


def test_unknown_executable_returns_127(fake_winutils_sudo, monkeypatch):
    monkeypatch.setattr(aliases, "locate_binary", lambda cmd: None)
    out, err, rc = win_sudo(["nosuchprog", "--flag"])
    assert out == ""
    assert 'cannot find executable "nosuchprog"' in err
    assert rc == 127
    assert fake_winutils_sudo == []


def test_resolved_binary_path_is_normalized(fake_winutils_sudo, monkeypatch):
    """Mixed-slash paths from PATH entries like ``~/.local/bin`` are normalized
    via ``os.path.normpath`` before being passed to ShellExecute (issue #5706).
    """
    raw_path = "foo/./bin/cp.exe"
    monkeypatch.setattr(aliases, "locate_binary", lambda cmd: raw_path)
    result = win_sudo(["cp", "-r", "a", "b"])
    assert result == "elevated"
    [(executable, args)] = fake_winutils_sudo
    assert executable == os.path.normpath(raw_path)
    assert executable != raw_path, "normpath should have collapsed '/./'"
    assert args == ["-r", "a", "b"]


def test_cmd_builtin_dispatched_via_cmd_exe(fake_winutils_sudo, monkeypatch):
    """``dir``/``copy``/... go through ``cmd /D /C CD <cwd> && <cmd>``."""
    monkeypatch.setattr(aliases, "locate_binary", lambda cmd: None)
    monkeypatch.setattr(aliases, "_find_cmd_exe", lambda: "X:\\sys\\cmd.exe")
    monkeypatch.setattr(aliases, "_get_cwd", lambda: "C:\\work")
    win_sudo(["dir", "/B"])
    [(executable, args)] = fake_winutils_sudo
    assert executable == "X:\\sys\\cmd.exe"
    assert args == ["/D", "/C", "CD", "C:\\work", "&&", "dir", "/B"]


def test_cmd_builtin_match_is_case_insensitive(fake_winutils_sudo, monkeypatch):
    monkeypatch.setattr(aliases, "locate_binary", lambda cmd: None)
    monkeypatch.setattr(aliases, "_find_cmd_exe", lambda: "cmd")
    monkeypatch.setattr(aliases, "_get_cwd", lambda: ".")
    win_sudo(["DIR"])
    [(_, args)] = fake_winutils_sudo
    assert args == ["/D", "/C", "CD", ".", "&&", "DIR"]


def test_resolved_binary_takes_precedence_over_cmd_builtin(
    fake_winutils_sudo, monkeypatch
):
    """If a real ``echo.exe`` exists on PATH, use that, not the cmd builtin."""
    monkeypatch.setattr(aliases, "locate_binary", lambda cmd: "C:\\bin\\echo.exe")
    win_sudo(["echo", "hi"])
    [(executable, args)] = fake_winutils_sudo
    assert executable == os.path.normpath("C:\\bin\\echo.exe")
    assert args == ["hi"]


def test_windows_cmd_aliases_is_frozen():
    """The constant must be a frozenset so callers cannot mutate it."""
    assert isinstance(WINDOWS_CMD_ALIASES, frozenset)
    assert "dir" in WINDOWS_CMD_ALIASES
    assert "echo" in WINDOWS_CMD_ALIASES
