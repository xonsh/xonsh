import os
import inspect
import pytest

from xonsh.aliases import xexec


@pytest.fixture
def mockexecvpe(monkeypatch):
    def mocked_execvpe(_command, _args, _env):
        pass

    monkeypatch.setattr(os, "execvpe", mocked_execvpe)


def test_noargs(mockexecvpe):
    assert xexec([]) == (None, "xonsh: exec: no args specified\n", 1)


def test_missing_command(mockexecvpe):
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
        "xonsh: exec: file not found: {}: {}" "\n".format(dummy_error_msg, command),
        1,
    )


def test_help(mockexecvpe):
    assert xexec(["-h"]) == inspect.getdoc(xexec)
    assert xexec(["--help"]) == inspect.getdoc(xexec)


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
