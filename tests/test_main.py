# -*- coding: utf-8 -*-
"""Tests the xonsh main function."""
from __future__ import unicode_literals, print_function
from contextlib import contextmanager

import builtins
import gc
import os
import os.path
import sys

import xonsh.main
from xonsh.main import XonshMode
from xonsh.environ import Env
import pytest
from tools import TEST_DIR


def Shell(*args, **kwargs):
    pass


@pytest.fixture
def shell(xonsh_builtins, monkeypatch):
    """Xonsh Shell Mock"""
    if hasattr(builtins, "__xonsh__"):
        builtins.__xonsh__.unlink_builtins()
        del builtins.__xonsh__
    for xarg in dir(builtins):
        if "__xonsh_" in xarg:
            delattr(builtins, xarg)
    gc.collect()
    Shell.shell_type_aliases = {"rl": "readline"}
    monkeypatch.setattr(xonsh.main, "Shell", Shell)


def test_premain_no_arg(shell, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    xonsh.main.premain([])
    assert builtins.__xonsh__.env.get("XONSH_LOGIN")


def test_premain_interactive(shell):
    xonsh.main.premain(["-i"])
    assert builtins.__xonsh__.env.get("XONSH_INTERACTIVE")


def test_premain_login_command(shell):
    xonsh.main.premain(["-l", "-c", 'echo "hi"'])
    assert builtins.__xonsh__.env.get("XONSH_LOGIN")


def test_premain_login(shell):
    xonsh.main.premain(["-l"])
    assert builtins.__xonsh__.env.get("XONSH_LOGIN")


def test_premain_D(shell):
    xonsh.main.premain(["-DTEST1=1616", "-DTEST2=LOL"])
    assert builtins.__xonsh__.env.get("TEST1") == "1616"
    assert builtins.__xonsh__.env.get("TEST2") == "LOL"


def test_premain_custom_rc(shell, tmpdir, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setitem(os.environ, "XONSH_CACHE_SCRIPTS", "False")
    f = tmpdir.join("wakkawakka")
    f.write("print('hi')")
    args = xonsh.main.premain(["--rc", f.strpath])
    assert args.mode == XonshMode.interactive
    assert f.strpath in builtins.__xonsh__.env.get("XONSHRC")


def test_no_rc_with_script(shell, tmpdir):
    args = xonsh.main.premain(["tests/sample.xsh"])
    assert not (args.mode == XonshMode.interactive)


def test_force_interactive_rc_with_script(shell, tmpdir):
    args = xonsh.main.premain(["-i", "tests/sample.xsh"])
    assert builtins.__xonsh__.env.get("XONSH_INTERACTIVE")


def test_force_interactive_custom_rc_with_script(shell, tmpdir, monkeypatch):
    """Calling a custom RC file on a script-call with the interactive flag
    should run interactively
    """
    monkeypatch.setitem(os.environ, "XONSH_CACHE_SCRIPTS", "False")
    f = tmpdir.join("wakkawakka")
    f.write("print('hi')")
    args = xonsh.main.premain(["-i", "--rc", f.strpath, "tests/sample.xsh"])
    assert args.mode == XonshMode.interactive
    assert f.strpath in builtins.__xonsh__.env.get("XONSHRC")


def test_custom_rc_with_script(shell, tmpdir):
    """Calling a custom RC file on a script-call without the interactive flag
    should not run interactively
    """
    f = tmpdir.join("wakkawakka")
    f.write("print('hi')")
    args = xonsh.main.premain(["--rc", f.strpath, "tests/sample.xsh"])
    assert not (args.mode == XonshMode.interactive)


def test_premain_no_rc(shell, tmpdir):
    xonsh.main.premain(["--no-rc", "-i"])
    assert not builtins.__xonsh__.env.get("XONSHRC")


@pytest.mark.parametrize(
    "arg", ["", "-i", "-vERSION", "-hAALP", "TTTT", "-TT", "--TTT"]
)
def test_premain_with_file_argument(arg, shell):
    xonsh.main.premain(["tests/sample.xsh", arg])
    assert not (builtins.__xonsh__.env.get("XONSH_INTERACTIVE"))


def test_premain_interactive__with_file_argument(shell):
    xonsh.main.premain(["-i", "tests/sample.xsh"])
    assert builtins.__xonsh__.env.get("XONSH_INTERACTIVE")


@pytest.mark.parametrize("case", ["----", "--hep", "-TT", "--TTTT"])
def test_premain_invalid_arguments(shell, case, capsys):
    with pytest.raises(SystemExit):
        xonsh.main.premain([case])
    assert "unrecognized argument" in capsys.readouterr()[1]


def test_premain_timings_arg(shell):
    xonsh.main.premain(["--timings"])


def test_xonsh_failback(shell, monkeypatch, monkeypatch_stderr):
    failback_checker = []

    def mocked_main(*args):
        raise Exception("A fake failure")

    monkeypatch.setattr(xonsh.main, "main_xonsh", mocked_main)

    def mocked_execlp(f, *args):
        failback_checker.append(f)
        failback_checker.append(args[0])

    monkeypatch.setattr(os, "execlp", mocked_execlp)
    monkeypatch.setattr(os.path, "exists", lambda x: True)
    monkeypatch.setattr(sys, "argv", ["xonsh", "-i"])

    @contextmanager
    def mocked_open(*args):
        yield ["/usr/bin/xonsh", "/usr/bin/screen", "bash", "/bin/xshell"]

    monkeypatch.setattr(builtins, "open", mocked_open)

    xonsh.main.main()
    assert failback_checker == ["/bin/xshell", "/bin/xshell"]


def test_xonsh_failback_single(shell, monkeypatch, monkeypatch_stderr):
    class FakeFailureError(Exception):
        pass

    def mocked_main(*args):
        raise FakeFailureError()

    monkeypatch.setattr(xonsh.main, "main_xonsh", mocked_main)
    monkeypatch.setattr(sys, "argv", ["xonsh", "-c", "echo", "foo"])

    with pytest.raises(FakeFailureError):
        xonsh.main.main()


def test_xonsh_failback_script_from_file(shell, monkeypatch, monkeypatch_stderr):
    checker = []

    def mocked_execlp(f, *args):
        checker.append(f)

    monkeypatch.setattr(os, "execlp", mocked_execlp)

    script = os.path.join(TEST_DIR, "scripts", "raise.xsh")
    monkeypatch.setattr(sys, "argv", ["xonsh", script])
    with pytest.raises(Exception):
        xonsh.main.main()
    assert len(checker) == 0
