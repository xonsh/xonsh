import pytest

from tests.tools import ON_WINDOWS
from xonsh.completers.base import complete_base
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    CommandArg,
    PythonContext,
)


CUR_DIR = "." if ON_WINDOWS else "./"  # for some reason this is what happens in `complete_path`


@pytest.fixture(autouse=True)
def setup(xonsh_builtins, xonsh_execer, monkeypatch):
    monkeypatch.setattr(xonsh_builtins.__xonsh__, "commands_cache", ["cool"])


def test_empty_line():
    completions = complete_base(
        CompletionContext(
            command=CommandContext((), 0),
            python=PythonContext("", 0)
        )
    )
    assert completions
    for exp in ["cool", CUR_DIR, "abs"]:
        assert exp in completions


def test_empty_subexpr():
    completions = complete_base(
        CompletionContext(
            command=CommandContext((), 0, subcmd_opening="$("),
            python=None
        )
    )
    assert completions
    for exp in ["cool", CUR_DIR]:
        assert exp in completions
    assert "abs" not in completions
