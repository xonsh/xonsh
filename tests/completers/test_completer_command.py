from xonsh.parsers.completion_context import CommandArg, CommandContext, CompletionContext
from xonsh.completers.completer import complete_completer


def test_options():
    assert complete_completer(CompletionContext(CommandContext(
        args=(CommandArg("completer"),), arg_index=1,
    ))) == {"add", "remove", "list", "help"}


def test_help_options():
    assert complete_completer(CompletionContext(CommandContext(
        args=(CommandArg("completer"),CommandArg("help")), arg_index=2,
    ))) == {"add", "remove", "list"}
