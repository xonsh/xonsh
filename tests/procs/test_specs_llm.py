"""Tests for Windows file-extension dispatch in specs.py."""

import os
import sys

import pytest

from xonsh.procs.specs import SubprocSpec, get_script_subproc_command
from xonsh.pytest.tools import ON_WINDOWS
from xonsh.tools import XonshError, chdir

pytestmark = pytest.mark.skipif(not ON_WINDOWS, reason="Windows-only")


def test_xsh_runs_in_xonsh(tmpdir, xession):
    script = tmpdir / "test.xsh"
    script.write_text("echo hello", encoding="utf-8")
    cmd = get_script_subproc_command(str(script), ["arg1"])
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "xonsh"]
    assert cmd[3] == str(script)
    assert cmd[4] == "arg1"


def test_py_runs_in_xonsh(tmpdir, xession):
    script = tmpdir / "test.py"
    script.write_text("print(1)", encoding="utf-8")
    cmd = get_script_subproc_command(str(script), [])
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "xonsh"]
    assert cmd[3] == str(script)


def test_vbs_uses_cmd_when_in_pathext(tmpdir, xession):
    script = tmpdir / "test.vbs"
    script.write_text('WScript.Echo "hi"', encoding="utf-8")
    with xession.env.swap(PATHEXT=[".VBS"]):
        cmd = get_script_subproc_command(str(script), [])
    assert cmd[:2] == ["cmd", "/c"]
    assert cmd[2] == str(script)


def test_vbs_returns_none_when_not_in_pathext(tmpdir, xession):
    script = tmpdir / "test.vbs"
    script.write_text('WScript.Echo "hi"', encoding="utf-8")
    with xession.env.swap(PATHEXT=[]):
        cmd = get_script_subproc_command(str(script), [])
    assert cmd is None


def test_unknown_text_file_returns_none(tmpdir, xession):
    script = tmpdir / "data.txt"
    script.write_text("hello", encoding="utf-8")
    with xession.env.swap(PATHEXT=[]):
        cmd = get_script_subproc_command(str(script), [])
    assert cmd is None


def test_unknown_with_shebang_uses_shebang(tmpdir, xession):
    script = tmpdir / "test.sh"
    script.write_text("#!/bin/bash\necho hi", encoding="utf-8")
    with xession.env.swap(PATHEXT=[]):
        cmd = get_script_subproc_command(str(script), [])
    assert cmd is not None
    assert "bash" in cmd[0]


def test_binary_returns_none(tmpdir, xession):
    """Binary files should return None (run directly via CreateProcess)."""
    binary = tmpdir / "app.dat"
    binary.write_binary(b"MZ\x00\x00")
    with xession.env.swap(PATHEXT=[]):
        cmd = get_script_subproc_command(str(binary), [])
    assert cmd is None


def test_resolve_does_not_error_on_binary(tmpdir, xession):
    """resolve_executable_commands must not raise for binary files
    even though get_script_subproc_command returns None."""
    bindir = tmpdir.mkdir("bin")
    exe = bindir / "myapp.exe"
    exe.write_binary(b"MZ\x90\x00\x03\x00\x00\x00")
    os.chmod(str(exe), 0o777)
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[".EXE"]):
        spec = SubprocSpec.build(["myapp.exe"])
        assert spec.binary_loc is not None


def test_xsh_found_in_path_by_bare_name(tmpdir, xession):
    """Typing 'myscript' should find 'myscript.xsh' in PATH and run
    it with xonsh, even when .XSH is not in PATHEXT."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "myscript.xsh").write_text("echo hi", encoding="utf-8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[]):
        spec = SubprocSpec.build(["myscript"])
        assert spec.cmd[0] == sys.executable
        assert spec.cmd[1:3] == ["-m", "xonsh"]


def test_py_found_in_path_by_bare_name(tmpdir, xession):
    """Typing 'myscript' should find 'myscript.py' in PATH and run
    it with xonsh, even when .PY is not in PATHEXT."""
    bindir = tmpdir.mkdir("bin")
    (bindir / "myscript.py").write_text("print(1)", encoding="utf-8")
    with xession.env.swap(PATH=[str(bindir)], PATHEXT=[]):
        spec = SubprocSpec.build(["myscript"])
        assert spec.cmd[0] == sys.executable
        assert spec.cmd[1:3] == ["-m", "xonsh"]


def test_unknown_file_with_path_prefix_errors(tmpdir, xession):
    """./unknown_file should raise XonshError on Windows."""
    script = tmpdir / "unknown_file"
    script.write_text("some data", encoding="utf-8")
    sep = os.path.sep
    with xession.env.swap(PATHEXT=[]), chdir(str(tmpdir)):
        with pytest.raises(XonshError, match="unknown file type"):
            SubprocSpec.build([f".{sep}unknown_file"])
