"""Tests for xonsh-native .xsh/.py extension handling on Windows."""

import os

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import (
    get_possible_names,
    is_executable_in_windows,
    locate_executable,
    locate_relative_path,
)
from xonsh.tools import chdir

pytestmark = pytest.mark.skipif(not ON_WINDOWS, reason="Windows-only")


def test_get_possible_names_empty_pathext_includes_known():
    """On Windows, even with empty PATHEXT, .xsh and .py are searched."""
    from xonsh.environ import Env

    env = Env(PATHEXT=[])
    result = get_possible_names("script", env)
    assert "script.xsh" in result
    assert "script.py" in result


def test_is_executable_recognises_xsh(tmpdir, xession):
    f = tmpdir / "script.xsh"
    f.write_text("echo hello", encoding="utf8")
    with xession.env.swap(PATHEXT=[]):
        assert is_executable_in_windows(str(f)) is True


def test_is_executable_recognises_py(tmpdir, xession):
    f = tmpdir / "script.py"
    f.write_text("print(1)", encoding="utf8")
    with xession.env.swap(PATHEXT=[]):
        assert is_executable_in_windows(str(f)) is True


def test_is_executable_rejects_unknown(tmpdir, xession):
    f = tmpdir / "data.txt"
    f.write_text("hello", encoding="utf8")
    with xession.env.swap(PATHEXT=[]):
        assert is_executable_in_windows(str(f)) is False


def test_locate_executable_finds_xsh_in_path(tmpdir, xession):
    """Bare name 'myscript' should find 'myscript.xsh' in PATH."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "myscript.xsh").write_text("echo hi", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[]):
        result = locate_executable("myscript")
        assert result is not None
        assert result.endswith("myscript.xsh")


def test_locate_executable_finds_py_in_path(tmpdir, xession):
    """Bare name 'myscript' should find 'myscript.py' in PATH."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "myscript.py").write_text("print(1)", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[]):
        result = locate_executable("myscript")
        assert result is not None
        assert result.endswith("myscript.py")


def test_locate_executable_pathext_before_known(tmpdir, xession):
    """PATHEXT extensions should be searched before xonsh-native ones."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "app.vbs").write_text("WScript.Echo 1", encoding="utf8")
    (bindir / "app.xsh").write_text("echo 1", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[".VBS"]):
        result = locate_executable("app")
        assert result is not None
        assert result.endswith("app.vbs")


def test_locate_executable_unknown_not_found(tmpdir, xession):
    """A file with no PATHEXT/known extension should not be found."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "datafile").write_text("data", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[]):
        assert locate_executable("datafile") is None


def test_locate_relative_xsh(tmpdir, xession):
    """./myscript should find ./myscript.xsh with empty PATHEXT."""
    (tmpdir / "myscript.xsh").write_text("echo hi", encoding="utf8")
    with xession.env.swap(PATH=[], PATHEXT=[]), chdir(str(tmpdir)):
        result = locate_relative_path(f".{os.sep}myscript", use_pathext=True)
        assert result is not None
        assert result.endswith("myscript.xsh")
