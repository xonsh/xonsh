import os
import shutil

import pytest

from xonsh.completers.bash import complete_from_bash
from xonsh.completers.tools import RichCompletion
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)
from xonsh.pytest.tools import skip_if_on_bsd, skip_if_on_darwin, skip_if_on_windows

if os.path.exists("/nix"):
    pytest.skip(
        "Skipping bash completion tests on Nix systems for future fixing. PR with fix is welcome!",
        allow_module_level=True,
    )

if shutil.which("bash") is None:
    # Every test in this module shells out to bash to drive bash-completion;
    # without the binary on PATH they all collapse into "set() == expected"
    # noise. Skip the module entirely on stripped build environments
    # (e.g. FreeBSD poudriere jails that don't install bash).
    pytest.skip(
        "bash not found on PATH — bash-completion tests need a real bash.",
        allow_module_level=True,
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
            {"testdir/", "'spaced dir/'"},
            0,
        ),
        # tar replaces "~/" with "/home/user/", the change should be rolledback by us.
        # Skipped on BSD: bsdtar's option set is a subset of GNU tar's, so the
        # expected list doesn't match what bash-completion produces there.
        pytest.param(
            CommandContext(args=(CommandArg("tar"),), arg_index=1, prefix="~/"),
            {"~/c", "~/u", "~/t", "~/d", "~/A", "~/r", "~/x"},
            2,
            marks=skip_if_on_bsd,
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


@skip_if_on_darwin
@skip_if_on_windows
@pytest.mark.parametrize(
    "command_context, completions, lprefix, exp_append_space",
    (
        # dd sta  ->  dd status=
        (
            CommandContext(args=(CommandArg("dd"),), arg_index=1, prefix="sta"),
            {"status="},
            3,
            False,
        ),
        # date --u  ->  date --utc
        # Skipped on BSD: BSD `date` doesn't accept GNU long options like
        # --utc, so the platform's bash-completion offers nothing here.
        pytest.param(
            CommandContext(args=(CommandArg("date"),), arg_index=1, prefix="--u"),
            {"--utc"},
            3,
            True,
            marks=skip_if_on_bsd,
        ),
        # dd status=pr -> dd status=progress
        (
            CommandContext(args=(CommandArg("dd"),), arg_index=1, prefix="status=pr"),
            {"progress"},
            2,
            True,
        ),
        # dd if=/et -> dd if=/etc/
        (
            CommandContext(args=(CommandArg("dd"),), arg_index=1, prefix="if=/et"),
            {"/etc/"},
            3,
            False,
        ),
        # dd of=/dev/nul -> dd of=/dev/null
        (
            CommandContext(args=(CommandArg("dd"),), arg_index=1, prefix="of=/dev/nul"),
            {"/dev/null"},
            8,
            True,
        ),
    ),
)
def test_equal_sign_arg(command_context, completions, lprefix, exp_append_space):
    bash_completions, bash_lprefix = complete_from_bash(
        CompletionContext(command_context)
    )
    assert bash_completions == completions and bash_lprefix == lprefix
    assert all(
        isinstance(comp, RichCompletion) and comp.append_space == exp_append_space
        for comp in bash_completions
    )


@pytest.fixture
def bash_completer(fake_process):
    fake_process.register_subprocess(
        command=["bash", fake_process.any()],
        # completion for "git push origin :dev-b"
        stdout=b"""\
complete -o bashdefault -o default -o nospace -F __git_wrap__git_main git
dev-branch
""",
    )

    return fake_process


# git push origin :dev-b<TAB>  ->  git push origin :dev-branch
def test_git_delete_remote_branch(bash_completer):
    command_context = CommandContext(
        args=(
            CommandArg("git"),
            CommandArg("push"),
            CommandArg("origin"),
        ),
        arg_index=3,
        prefix=":dev-b",
    )
    bash_completions, bash_lprefix = complete_from_bash(
        CompletionContext(command_context)
    )
    assert bash_completions == {"dev-branch"} and bash_lprefix == 5
    assert all(
        isinstance(comp, RichCompletion) and comp.append_space is False
        for comp in bash_completions
    )
