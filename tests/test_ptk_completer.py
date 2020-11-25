import pytest
from unittest.mock import MagicMock
from prompt_toolkit.completion import Completion as PTKCompletion

from xonsh.aliases import Aliases
from xonsh.completers.tools import RichCompletion
from xonsh.ptk_shell.completer import PromptToolkitCompleter


@pytest.mark.parametrize(
    "completion, lprefix, ptk_completion",
    [
        (RichCompletion("x", 0, "x()", "func"), 0, None),
        (RichCompletion("x", 1, "xx", "instance"), 0, None),
        (
            RichCompletion("x", description="wow"),
            5,
            PTKCompletion(RichCompletion("x"), -5, "x", "wow"),
        ),
        (RichCompletion("x"), 5, PTKCompletion(RichCompletion("x"), -5, "x")),
        ("x", 5, PTKCompletion("x", -5, "x")),
    ],
)
def test_rich_completion(
    completion, lprefix, ptk_completion, monkeypatch, xonsh_builtins
):
    xonsh_completer_mock = MagicMock()
    xonsh_completer_mock.complete.return_value = {completion}, lprefix

    ptk_completer = PromptToolkitCompleter(xonsh_completer_mock, None, None)
    ptk_completer.reserve_space = lambda: None
    ptk_completer.suggestion_completion = lambda _, __: None

    document_mock = MagicMock()
    document_mock.text = ""
    document_mock.current_line = ""
    document_mock.cursor_position_col = 0

    monkeypatch.setattr("builtins.aliases", Aliases())

    completions = list(ptk_completer.get_completions(document_mock, MagicMock()))
    if isinstance(completion, RichCompletion) and not ptk_completion:
        assert completions == [
            PTKCompletion(
                completion,
                -completion.prefix_len,
                completion.display,
                completion.description,
            )
        ]
    else:
        assert completions == [ptk_completion]
