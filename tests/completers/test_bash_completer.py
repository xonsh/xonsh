import pytest

from tests.tools import skip_if_on_windows, skip_if_on_darwin

from xonsh.completers.bash import complete_from_bash
from xonsh.parsers.completion_context import CompletionContext, CommandContext, CommandArg


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    (tmp_path / "testdir").mkdir()
    (tmp_path / "spaced dir").mkdir()
    monkeypatch.chdir(str(tmp_path))



@skip_if_on_darwin
@skip_if_on_windows
@pytest.mark.parametrize("command_context, completions, lprefix", (
        (CommandContext(args=(CommandArg("bash"),), arg_index=1, prefix="--deb"), {"--debug", "--debugger"}, 5),
        (CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix=""), {"'testdir/'", "'spaced dir/'"}, 0),
        (CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix="", opening_quote="'"), {"'testdir/'", "'spaced dir/'"}, 1),
        pytest.param(CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix="test", opening_quote="'"), {"'testdir/'"}, 1,
            marks=pytest.mark.skip("bash completions don't consider the opening quote")),
))
def test_bash_completer(command_context, completions, lprefix, xonsh_builtins, monkeypatch):
    if not xonsh_builtins.__xonsh__.env.get("BASH_COMPLETIONS"):
        monkeypatch.setitem(xonsh_builtins.__xonsh__.env, "BASH_COMPLETIONS", ["/usr/share/bash-completion/bash_completion"])
    bash_completions, bash_lprefix = complete_from_bash(CompletionContext(command_context))
    assert bash_completions == completions and bash_lprefix == lprefix

