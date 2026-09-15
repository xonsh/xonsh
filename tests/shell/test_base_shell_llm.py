"""LLM-generated tests for ``xonsh.shells.base_shell``."""

import errno
import os

import pytest

from xonsh.built_ins import XSH
from xonsh.platform import ON_WINDOWS
from xonsh.shells.base_shell import BaseShell


def _raiser(exc):
    def raise_it(*args, **kwargs):
        raise exc

    return raise_it


@pytest.mark.parametrize(
    "exc",
    [
        FileNotFoundError(errno.ENOENT, "No such file or directory"),
        PermissionError(errno.EPERM, "Operation not permitted"),
        PermissionError(errno.EACCES, "Permission denied"),
        OSError(errno.EIO, "Input/output error"),
    ],
    ids=["enoent", "eperm", "eacces", "eio"],
)
def test_precmd_survives_unreachable_cwd(
    exc, xession, xonsh_execer, monkeypatch, tmpdir
):
    """``os.getcwd()`` fails for more reasons than a plain deletion: an
    ancestor that stopped being readable, an unmounted volume, or a macOS
    sandbox/TCC denial all arrive as ``PermissionError``. None of them may
    escape ``precmd()`` -- an exception here reaches ``xonsh.main`` and gets
    the whole interactive session replaced by another shell.
    """
    shell = BaseShell(xonsh_execer, None)
    xession.env["PWD"] = str(tmpdir)
    monkeypatch.setattr(os, "getcwd", _raiser(exc))

    assert shell.precmd("echo test") == "echo test"
    # $PWD is xonsh's own record of where the session is, so it beats
    # pretending the command ran in the home directory.
    assert shell.precwd == str(tmpdir)


def test_precmd_falls_back_to_home_without_pwd(xession, xonsh_execer, monkeypatch):
    """With no usable ``$PWD`` left there is nothing better than ``~``."""
    shell = BaseShell(xonsh_execer, None)
    xession.env["PWD"] = ""
    monkeypatch.setattr(os, "getcwd", _raiser(PermissionError(errno.EPERM, "nope")))

    shell.precmd("echo test")

    assert shell.precwd == os.path.expanduser("~")


def test_precmd_falls_back_to_home_without_env(xession, xonsh_execer, monkeypatch):
    """The session may not carry an ``env`` at all (bare ``XSH``)."""
    shell = BaseShell(xonsh_execer, None)
    monkeypatch.setattr(os, "getcwd", _raiser(PermissionError(errno.EPERM, "nope")))
    monkeypatch.setattr(XSH, "env", None)

    shell.precmd("echo test")

    assert shell.precwd == os.path.expanduser("~")


def _shell_with_title(xession, xonsh_execer):
    shell = BaseShell(xonsh_execer, None)
    xession.env["TERM"] = "xterm-256color"
    xession.env["TITLE"] = "hello"
    return shell


@pytest.mark.skipif(ON_WINDOWS, reason="Windows sets the title through the console API")
def test_settitle_writes_osc_sequence_to_tty_stdout(
    xession, xonsh_execer, monkeypatch, capfdbinary
):
    shell = _shell_with_title(xession, xonsh_execer)
    monkeypatch.setattr(os, "isatty", lambda fd: True)

    shell.settitle()

    out, _ = capfdbinary.readouterr()
    assert out == b"\x1b]0;hello\x07"


@pytest.mark.skipif(ON_WINDOWS, reason="Windows sets the title through the console API")
def test_settitle_skips_non_tty_stdout(xession, xonsh_execer, monkeypatch, capfdbinary):
    """``xonsh -i -c cmd | consumer`` and ``xonsh -i -c cmd > file`` must not
    leak the title escape into the captured output: the sequence lands ahead
    of every subprocess command's output and corrupts anything that parses it.
    """
    shell = _shell_with_title(xession, xonsh_execer)
    monkeypatch.setattr(os, "isatty", lambda fd: False)

    shell.settitle()

    out, _ = capfdbinary.readouterr()
    assert out == b""
