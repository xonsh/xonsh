from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)
from xonsh.completers.xompletions import complete_xontrib
import pytest


@pytest.mark.parametrize(
    "args, prefix, exp",
    [
        (
            "xonfig",
            "-",
            {"-h", "--help"},
        ),
        (
            "xonfig colors",
            "b",
            {"blue", "brown"},
        ),
    ],
)
def test_xonfig(args, prefix, exp, xsh_with_aliases, monkeypatch, check_completer):
    from xonsh import xonfig

    monkeypatch.setattr(xonfig, "color_style_names", lambda: ["blue", "brown", "other"])
    assert check_completer(args, prefix=prefix) == exp


def test_xontrib():
    assert complete_xontrib(
        CompletionContext(
            CommandContext(args=(CommandArg("xontrib"),), arg_index=1, prefix="l")
        )
    ) == {"list", "load"}
