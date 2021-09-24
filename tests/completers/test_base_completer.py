import pytest

from tests.tools import ON_WINDOWS
from xonsh.completers.base import complete_base
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    PythonContext,
)


CUR_DIR = (
    "." if ON_WINDOWS else "./"
)  # for some reason this is what happens in `complete_path`


@pytest.fixture(autouse=True)
def setup(xession, xonsh_execer, monkeypatch):
    monkeypatch.setattr(xession, "commands_cache", ["cool"])


def test_empty_line():
    completions = complete_base(
        CompletionContext(command=CommandContext((), 0), python=PythonContext("", 0))
    )
    assert completions
    for exp in ["cool", "abs"]:
        assert exp in completions


def test_empty_subexpr():
    completions = complete_base(
        CompletionContext(
            command=CommandContext((), 0, subcmd_opening="$("), python=None
        )
    )
    assert completions
    for exp in ["cool"]:
        assert exp in completions
    assert "abs" not in completions
