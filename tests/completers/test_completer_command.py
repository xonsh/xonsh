import pytest

from xonsh.completers.completer import complete_argparser_aliases
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)


@pytest.fixture
def xsh_with_aliases(xession, monkeypatch):
    from xonsh.aliases import Aliases, make_default_aliases

    xsh = xession
    monkeypatch.setattr(xsh, "aliases", Aliases(make_default_aliases()))
    return xsh


def check_completer(args: str, exp: set, **kwargs):
    cmds = tuple(CommandArg(i) for i in args.split(" "))
    arg_index = len(cmds)
    completions = complete_argparser_aliases(
        CompletionContext(CommandContext(args=cmds, arg_index=arg_index, **kwargs))
    )
    comp_values = {getattr(i, "value", i) for i in completions}
    assert comp_values == exp


@pytest.mark.parametrize(
    "args, exp",
    [
        (
            "completer",
            {"add", "remove", "rm", "list", "ls", "--help", "-h"},
        ),
        (
            "completer add",
            {"--help", "-h"},
        ),
        (
            "completer add newcompleter",
            {"--help", "-h", "three", "four"},
        ),
        (
            "completer add newcompleter three",
            {"<one", "--help", ">two", ">one", "<two", "end", "-h", "start"},
        ),
        (
            "completer remove",
            {"--help", "-h", "one", "two"},
        ),
        (
            "completer list",
            {"--help", "-h"},
        ),
    ],
)
def test_completer_command(args, exp, xsh_with_aliases, monkeypatch):
    xsh = xsh_with_aliases
    monkeypatch.setattr(xsh, "completers", {"one": 1, "two": 2})
    monkeypatch.setattr(xsh, "ctx", {"three": lambda: 1, "four": lambda: 2})
    check_completer(args, exp)
