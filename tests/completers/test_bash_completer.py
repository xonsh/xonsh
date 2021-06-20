import pytest

from tests.tools import skip_if_on_windows, skip_if_on_darwin

from xonsh.completers.tools import RichCompletion
from xonsh.completers.bash import complete_from_bash
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    CommandArg,
)


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path, xession):
    if not xession.env.get("BASH_COMPLETIONS"):
        monkeypatch.setitem(
            xession.env,
            "BASH_COMPLETIONS",
            ["/usr/share/bash-completion/bash_completion"],
        )

    (tmp_path / "testdir").mkdir()
    (tmp_path / "spaced dir").mkdir()
    monkeypatch.chdir(str(tmp_path))


@skip_if_on_darwin
@skip_if_on_windows
@pytest.mark.parametrize(
    "command_context, completions, lprefix",
    (
        (
            CommandContext(args=(CommandArg("bash"),), arg_index=1, prefix="--deb"),
            {"--debug", "--debugger"},
            5,
        ),
        (
            CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix=""),
            {"'testdir/'", "'spaced dir/'"},
            0,
        ),
        (
            CommandContext(
                args=(CommandArg("ls"),), arg_index=1, prefix="", opening_quote="'"
            ),
            {"'testdir/'", "'spaced dir/'"},
            1,
        ),
    ),
)
def test_bash_completer(command_context, completions, lprefix):
    bash_completions, bash_lprefix = complete_from_bash(
        CompletionContext(command_context)
    )
    assert bash_completions == completions and bash_lprefix == lprefix


@skip_if_on_darwin
@skip_if_on_windows
@pytest.mark.parametrize(
    "command_context, completions, lprefix",
    (
        # ls /pro<TAB>  ->  ls /proc/
        (
            CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix="/pro"),
            {"/proc/"},
            4,
        ),
        # ls '/pro<TAB>  ->  ls '/proc/'
        (
            CommandContext(
                args=(CommandArg("ls"),), arg_index=1, prefix="/pro", opening_quote="'"
            ),
            {"'/proc/'"},
            5,
        ),
        # ls '/pro<TAB>'  ->  ls '/proc/'
        (
            CommandContext(
                args=(CommandArg("ls"),),
                arg_index=1,
                prefix="/pro",
                opening_quote="'",
                closing_quote="'",
            ),
            {"'/proc/"},
            5,
        ),
        # ls '/pro'<TAB>  ->  ls '/proc/'
        (
            CommandContext(
                args=(CommandArg("ls"),),
                arg_index=1,
                prefix="/pro",
                opening_quote="'",
                closing_quote="'",
                is_after_closing_quote=True,
            ),
            {"'/proc/'"},
            6,
        ),
        # ls """/pro"""<TAB>  ->  ls """/proc/"""
        (
            CommandContext(
                args=(CommandArg("ls"),),
                arg_index=1,
                prefix="/pro",
                opening_quote='"""',
                closing_quote='"""',
                is_after_closing_quote=True,
            ),
            {'"""/proc/"""'},
            10,
        ),
        # Completions that have to be quoted:
        # ls ./sp  ->  ls './spaced dir/'
        (
            CommandContext(args=(CommandArg("ls"),), arg_index=1, prefix="./sp"),
            {"'./spaced dir/'"},
            4,
        ),
        # ls './sp<TAB>  ->  ls './spaced dir/'
        (
            CommandContext(
                args=(CommandArg("ls"),), arg_index=1, prefix="./sp", opening_quote="'"
            ),
            {"'./spaced dir/'"},
            5,
        ),
        # ls './sp<TAB>'  ->  ls './spaced dir/'
        (
            CommandContext(
                args=(CommandArg("ls"),),
                arg_index=1,
                prefix="./sp",
                opening_quote="'",
                closing_quote="'",
            ),
            {"'./spaced dir/"},
            5,
        ),
        # ls './sp'<TAB>  ->  ls './spaced dir/'
        (
            CommandContext(
                args=(CommandArg("ls"),),
                arg_index=1,
                prefix="./sp",
                opening_quote="'",
                closing_quote="'",
                is_after_closing_quote=True,
            ),
            {"'./spaced dir/'"},
            6,
        ),
    ),
)
def test_quote_handling(command_context, completions, lprefix):
    bash_completions, bash_lprefix = complete_from_bash(
        CompletionContext(command_context)
    )
    assert bash_completions == completions and bash_lprefix == lprefix
    assert all(
        isinstance(comp, RichCompletion) and not comp.append_closing_quote
        for comp in bash_completions
    )  # make sure the completer handles the closing quote by itself


@skip_if_on_darwin
@skip_if_on_windows
def test_bash_completer_empty_prefix():
    context = CompletionContext(
        CommandContext(args=(CommandArg("git"),), arg_index=1, prefix="")
    )
    bash_completions, bash_lprefix = complete_from_bash(context)
    assert {"clean", "show"}.issubset(bash_completions)
