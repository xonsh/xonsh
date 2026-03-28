import os

import pytest

from xonsh.aliases import xexec


@pytest.fixture(autouse=True)
def auto_use_xession(xession):
    return xession


@pytest.fixture
def mockexecvpe(monkeypatch):
    def mocked_execvpe(_command, _args, _env):
        pass

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)


def test_missing_command(mockexecvpe):
    assert xexec([]) == (None, "xonsh: exec: no command specified\n", 1)
    assert xexec(["-a", "foo"]) == (None, "xonsh: exec: no command specified\n", 1)
    assert xexec(["-c"]) == (None, "xonsh: exec: no command specified\n", 1)
    assert xexec(["-l"]) == (None, "xonsh: exec: no command specified\n", 1)


def test_command_not_found(monkeypatch):
    dummy_error_msg = (
        "This is dummy error message, file not found or something like that"
    )
    command = "non_existing_command"

    def mocked_execvpe(_command, _args, _env):
        raise FileNotFoundError(2, dummy_error_msg)

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)

    assert xexec([command]) == (
        None,
        f"xonsh: exec: file not found: {dummy_error_msg}: {command}\n",
        1,
    )


@pytest.mark.parametrize("cmd", ["-h", "--help"])
def test_help(cmd, mockexecvpe, capsys, mocker):
    usage = "usage: xexec [-h] [-l] [-c] [-a NAME] ..."
    exit_mock = mocker.patch("argparse._sys.exit")
    xexec([cmd])
    cap = capsys.readouterr()

    assert exit_mock.called
    assert usage in cap.out


def test_a_switch(monkeypatch):
    called = {}

    def mocked_execvpe(command, args, env):
        called.update({"command": command, "args": args, "env": env})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)
    proc_name = "foo"
    command = "bar"
    command_args = ["1"]
    xexec(["-a", proc_name, command] + command_args)
    assert called["command"] == command
    assert called["args"][0] == proc_name
    assert len(called["args"]) == len([command] + command_args)


def test_l_switch(monkeypatch):
    called = {}

    def mocked_execvpe(command, args, env):
        called.update({"command": command, "args": args, "env": env})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)
    command = "bar"
    xexec(["-l", command, "1"])

    assert called["args"][0].startswith("-")


def test_c_switch(monkeypatch):
    called = {}

    def mocked_execvpe(command, args, env):
        called.update({"command": command, "args": args, "env": env})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)
    command = "sleep"
    xexec(["-c", command, "1"])
    assert called["env"] == {}


def test_alias_stack_cleared(monkeypatch, xession):
    """exec must not pass __ALIAS_STACK to the new process.

    Regression test for #5216 / #5709: when a xonsh script does
    ``exec ./other_script.xsh`` and that script also uses ``exec``,
    the inherited __ALIAS_STACK caused a false "Recursive calls to exec"
    error.
    """
    called = {}

    def mocked_execvpe(command, args, env):
        called.update({"command": command, "args": args, "env": env})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)

    # Simulate being inside an exec alias call
    xession.env["__ALIAS_STACK"] = ":exec"
    xession.env["__ALIAS_NAME"] = "exec"

    xexec(["bash"])

    assert "__ALIAS_STACK" not in called["env"]
    assert "__ALIAS_NAME" not in called["env"]


def test_exec_script_shebang_fallback(monkeypatch, tmp_path):
    """exec on a script file should parse the shebang and use the interpreter.

    os.execvpe raises ENOEXEC (errno 8) for non-binary files.  xexec
    should fall back to get_script_subproc_command which parses the shebang.
    """
    calls = []

    def mocked_execvpe(command, args, env):
        if command.endswith(".xsh"):
            raise OSError(8, "Exec format error")
        calls.append({"command": command, "args": args})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)

    script = tmp_path / "test.xsh"
    script.write_text("#!/usr/bin/env xonsh\necho hello\n")
    script.chmod(0o755)

    xexec([str(script)])

    assert len(calls) == 1
    # The shebang fallback must invoke a different command than the script
    # itself.  The exact interpreter varies by platform (e.g. "/usr/bin/env"
    # on POSIX, "python" on Windows).
    assert calls[0]["command"] != str(script)
    assert str(script) in calls[0]["args"]


def test_exec_script_no_shebang_defaults_to_xonsh(monkeypatch, tmp_path):
    """exec on a script without shebang should default to xonsh."""
    calls = []

    def mocked_execvpe(command, args, env):
        if command.endswith(".xsh"):
            raise OSError(8, "Exec format error")
        calls.append({"command": command, "args": args})

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)

    script = tmp_path / "test.xsh"
    script.write_text("echo hello\n")
    script.chmod(0o755)

    xexec([str(script)])

    assert len(calls) == 1
    # Must not try to execute the script directly again
    assert calls[0]["command"] != str(script)


def test_exec_nonexistent_file(monkeypatch):
    """exec on a non-existent file should return an error."""

    def mocked_execvpe(command, args, env):
        raise OSError(2, "No such file or directory")

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)

    result = xexec(["/tmp/nonexistent_file"])
    assert result[2] == 1
    assert "file not found" in result[1]
