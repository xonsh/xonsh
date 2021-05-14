from unittest.mock import Mock

import pytest

from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandArg,
    CommandContext,
)

from tests.tools import ON_WINDOWS, skip_if_on_windows, completions_from_result

from xonsh.completer import Completer
from xonsh.completers.commands import complete_command, complete_skipper


@pytest.fixture(autouse=True)
def xs_orig_commands_cache(xession, monkeypatch):
    monkeypatch.setattr(
        xession.commands_cache,
        "locate_binary",
        xession.commands_cache.orig_locate_binary,
    )


def test_complete_command(completion_context_parse):
    if ON_WINDOWS:
        command = "dir.exe"
    else:
        command = "grep"

    assert command in complete_command(
        completion_context_parse(command[:-1], len(command) - 1).command
    )


@skip_if_on_windows
def test_skipper_command(completion_context_parse):
    assert "grep" in completions_from_result(
        complete_skipper(completion_context_parse("sudo gre", 8))
    )


@skip_if_on_windows
def test_skipper_arg(completion_context_parse, xession, monkeypatch):
    monkeypatch.setattr(xession.shell.shell, "completer", Completer(), raising=False)
    bash_completer_mock = Mock()
    monkeypatch.setattr(xession, "completers", {"bash": bash_completer_mock})

    bash_completer_mock.return_value = {"--count "}

    assert "--count " in completions_from_result(
        complete_skipper(completion_context_parse(f"sudo grep --coun", 16))
    )

    call_args = bash_completer_mock.call_args[0]
    assert len(call_args) == 1

    context = call_args[0]
    assert isinstance(context, CompletionContext)
    assert context.command == CommandContext(
        args=(CommandArg("grep"),), arg_index=1, prefix="--coun"
    )
