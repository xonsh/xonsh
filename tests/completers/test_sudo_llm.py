"""Tests for the ``sudo`` xompletion."""

from unittest.mock import Mock

import pytest

from xompletions.sudo import _find_inner_command_position, xonsh_complete
from xonsh.completer import Completer
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)
from xonsh.pytest.tools import completions_from_result, skip_if_on_windows


def _args(*vals):
    return tuple(CommandArg(v) for v in vals)


@pytest.mark.parametrize(
    "args, expected",
    [
        # Inner command not yet typed.
        (_args("sudo"), 1),
        (_args("sudo", "-E"), 2),
        (_args("sudo", "-u", "root"), 3),
        (_args("sudo", "--"), 2),
        # Inner command present.
        (_args("sudo", "ls"), 1),
        (_args("sudo", "-E", "ls"), 2),
        (_args("sudo", "--", "ls"), 2),
        (_args("sudo", "-u", "root", "ls"), 3),
        (_args("sudo", "--user=root", "ls"), 2),
        (_args("sudo", "--user", "root", "ls"), 3),
        (_args("sudo", "VAR=1", "ls"), 2),
        (_args("sudo", "VAR=1", "OTHER=2", "ls"), 3),
        # Composite: flag + env-var + flag-with-arg + inner command.
        (_args("sudo", "-E", "VAR=1", "-u", "root", "ls"), 5),
        # Multiple flags without args.
        (_args("sudo", "-E", "-H", "ls"), 3),
        # ``--`` terminates options even if more dashes follow inside the inner command.
        (_args("sudo", "--", "ls", "--color"), 2),
    ],
)
def test_find_inner_command_position(args, expected):
    assert _find_inner_command_position(args) == expected


def test_no_completion_for_flag_prefix(completion_context_parse):
    """``sudo -<Tab>`` defers to the man completer."""
    ctx = completion_context_parse("sudo -", 6).command
    assert xonsh_complete(ctx) is None


def test_no_completion_for_long_flag_prefix(completion_context_parse):
    """``sudo --u<Tab>`` defers — long flags are man's job."""
    ctx = completion_context_parse("sudo --u", 8).command
    assert xonsh_complete(ctx) is None


def test_no_completion_for_flag_value_slot(completion_context_parse):
    """``sudo -u <Tab>`` — username slot, not the inner command."""
    ctx = completion_context_parse("sudo -u ", 8).command
    assert xonsh_complete(ctx) is None


def test_no_completion_for_long_flag_value_slot(completion_context_parse):
    """``sudo --user <Tab>`` — same as the short form."""
    ctx = completion_context_parse("sudo --user ", 12).command
    assert xonsh_complete(ctx) is None


@skip_if_on_windows
def test_complete_inner_command_plain(completion_context_parse, xession):
    """``sudo gre<Tab>`` lists commands matching ``gre`` (regression coverage
    for the path that used to live in ``complete_skipper``)."""
    ctx = completion_context_parse("sudo gre", 8).command
    assert "grep" in completions_from_result(xonsh_complete(ctx))


@skip_if_on_windows
def test_complete_inner_command_after_double_dash(completion_context_parse, xession):
    """``sudo -- gre<Tab>`` — the ``--`` must not be treated as the command."""
    ctx = completion_context_parse("sudo -- gre", 11).command
    assert "grep" in completions_from_result(xonsh_complete(ctx))


@skip_if_on_windows
def test_complete_inner_command_after_double_dash_empty(
    completion_context_parse, xession
):
    """``sudo -- <Tab>`` — empty prefix after the option terminator still offers commands."""
    ctx = completion_context_parse("sudo -- ", 8).command
    completions = completions_from_result(xonsh_complete(ctx))
    assert "grep" in completions


@skip_if_on_windows
def test_complete_inner_command_after_flag_with_value(
    completion_context_parse, xession
):
    """``sudo -u root gre<Tab>`` — flag and its value are skipped."""
    ctx = completion_context_parse("sudo -u root gre", 16).command
    assert "grep" in completions_from_result(xonsh_complete(ctx))


@skip_if_on_windows
def test_complete_inner_command_after_long_flag_with_value(
    completion_context_parse, xession
):
    """``sudo --user=root gre<Tab>`` — embedded ``=`` consumes the value."""
    ctx = completion_context_parse("sudo --user=root gre", 20).command
    assert "grep" in completions_from_result(xonsh_complete(ctx))


@skip_if_on_windows
def test_complete_inner_command_after_env_assign(completion_context_parse, xession):
    """``sudo VAR=1 gre<Tab>`` — env-var assignments are not commands."""
    ctx = completion_context_parse("sudo VAR=1 gre", 14).command
    assert "grep" in completions_from_result(xonsh_complete(ctx))


@skip_if_on_windows
def test_delegate_to_inner_command_args(completion_context_parse, xession, monkeypatch):
    """``sudo grep --coun<Tab>`` re-enters the pipeline with ``grep`` as the head."""
    monkeypatch.setattr(xession.shell.shell, "completer", Completer(), raising=False)
    bash_completer_mock = Mock(return_value={"--count "})
    monkeypatch.setattr(xession, "_completers", {"bash": bash_completer_mock})

    ctx = completion_context_parse("sudo grep --coun", 16).command
    assert "--count " in completions_from_result(xonsh_complete(ctx))

    call_args = bash_completer_mock.call_args[0]
    assert len(call_args) == 1
    inner_ctx = call_args[0]
    assert isinstance(inner_ctx, CompletionContext)
    assert inner_ctx.command == CommandContext(
        args=(CommandArg("grep"),), arg_index=1, prefix="--coun"
    )


@skip_if_on_windows
def test_delegate_after_double_dash_to_inner_command_args(
    completion_context_parse, xession, monkeypatch
):
    """``sudo -- grep --coun<Tab>`` — both sudo and ``--`` are stripped before delegation."""
    monkeypatch.setattr(xession.shell.shell, "completer", Completer(), raising=False)
    bash_completer_mock = Mock(return_value={"--count "})
    monkeypatch.setattr(xession, "_completers", {"bash": bash_completer_mock})

    ctx = completion_context_parse("sudo -- grep --coun", 19).command
    assert "--count " in completions_from_result(xonsh_complete(ctx))

    inner_ctx = bash_completer_mock.call_args[0][0]
    assert inner_ctx.command == CommandContext(
        args=(CommandArg("grep"),), arg_index=1, prefix="--coun"
    )


@skip_if_on_windows
def test_delegate_after_flag_with_value_to_inner_command_args(
    completion_context_parse, xession, monkeypatch
):
    """``sudo -u root grep --coun<Tab>`` — flag, value, and sudo are all stripped."""
    monkeypatch.setattr(xession.shell.shell, "completer", Completer(), raising=False)
    bash_completer_mock = Mock(return_value={"--count "})
    monkeypatch.setattr(xession, "_completers", {"bash": bash_completer_mock})

    ctx = completion_context_parse("sudo -u root grep --coun", 24).command
    assert "--count " in completions_from_result(xonsh_complete(ctx))

    inner_ctx = bash_completer_mock.call_args[0][0]
    assert inner_ctx.command == CommandContext(
        args=(CommandArg("grep"),), arg_index=1, prefix="--coun"
    )
