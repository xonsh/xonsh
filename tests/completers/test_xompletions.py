from xonsh.parsers.completion_context import CommandArg, CommandContext, CompletionContext
from xonsh.completers.xompletions import complete_xonfig, complete_xontrib


def test_xonfig():
    assert complete_xonfig(CompletionContext(CommandContext(
        args=(CommandArg("xonfig"),), arg_index=1, prefix="-"
    ))) == {"-h"}


def test_xonfig_colors(monkeypatch):
    monkeypatch.setattr("xonsh.tools.color_style_names", lambda: ["blue", "brown", "other"])
    assert complete_xonfig(CompletionContext(CommandContext(
        args=(CommandArg("xonfig"), CommandArg("colors")), arg_index=2, prefix="b"
    ))) == {"blue", "brown"}


def test_xontrib():
    assert complete_xontrib(CompletionContext(CommandContext(
        args=(CommandArg("xontrib"),), arg_index=1, prefix="l"
    ))) == {"list", "load"}
