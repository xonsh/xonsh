"""Tests for the ``git`` xompletion."""

import pytest

import xompletions.git as xgit
from xonsh.pytest.tools import completions_from_result, skip_if_not_has

_LIST_CMDS_ARGS = ("--list-cmds=main,others,alias",)
_CONFIG_ARGS = ("config", "-z", "--get-regexp", r"^alias\.")
_REFS_ARGS = (
    "for-each-ref",
    "--format=%(refname:short)",
    "refs/heads/",
    "refs/tags/",
    "refs/remotes/",
)

_GIT_OUTPUTS = {
    _LIST_CMDS_ARGS: "add\nbranch\ncheckout\nstatus\nbr\nco\ngraph\nsh\nst\n",
    _CONFIG_ARGS: (
        "alias.co\ncheckout\x00"
        "alias.st\nstatus --short\x00"
        "alias.br\nbranch\x00"
        "alias.sh\n!echo hi\x00"
        "alias.graph\nlog --graph\n--oneline\x00"
    ),
    _REFS_ARGS: "main\ndev-branch\n",
}


@pytest.fixture
def git_calls(monkeypatch):
    """Replace ``_run_git`` with a canned fake and record every call."""
    calls = []

    def fake_run_git(*args):
        calls.append(args)
        if args in _GIT_OUTPUTS:
            return _GIT_OUTPUTS[args]
        if args[-1] == "--git-completion-helper":
            return f"--opt-for-{args[0]} --force"
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(xgit, "_run_git", fake_run_git)
    return calls


def _complete(completion_context_parse, line):
    ctx = completion_context_parse(line, len(line)).command
    return xgit.xonsh_complete(ctx)


def test_command_position_is_skipped(git_calls, completion_context_parse):
    ctx = completion_context_parse("git", 3).command
    assert xgit.xonsh_complete(ctx) is None
    assert git_calls == []


def test_subcommand_list_includes_aliases(git_calls, completion_context_parse):
    comps = completions_from_result(_complete(completion_context_parse, "git "))
    assert {"checkout", "status", "co", "st", "br"} <= {str(c) for c in comps}


@pytest.mark.parametrize(
    "name, body",
    [
        ("co", "checkout"),
        ("st", "status --short"),
        # multi-line alias bodies are shown on one line
        ("graph", "log --graph --oneline"),
        # real subcommands carry no description
        ("checkout", ""),
    ],
)
def test_alias_body_is_description(name, body, git_calls, completion_context_parse):
    comps = completions_from_result(_complete(completion_context_parse, "git "))
    by_value = {str(c): c for c in comps}
    assert by_value[name].description == body


def test_subcommand_list_without_aliases(monkeypatch, completion_context_parse):
    """``git config`` exits non-zero when no aliases are configured."""

    def fake_run_git(*args):
        if args == _LIST_CMDS_ARGS:
            return "add\ncheckout\n"
        if args == _CONFIG_ARGS:
            return None
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(xgit, "_run_git", fake_run_git)
    comps = completions_from_result(_complete(completion_context_parse, "git "))
    assert {str(c) for c in comps} == {"add", "checkout"}


@pytest.mark.parametrize("subcmd", ["checkout", "co", "graph"])
def test_ref_completion_resolves_aliases(subcmd, git_calls, completion_context_parse):
    comps = completions_from_result(
        _complete(completion_context_parse, f"git {subcmd} ")
    )
    assert {str(c) for c in comps} == {"main", "dev-branch"}


def test_option_completion_resolves_aliases(git_calls, completion_context_parse):
    comps = completions_from_result(_complete(completion_context_parse, "git st -"))
    # ``st`` resolved to ``status`` before calling ``--git-completion-helper``
    assert {str(c) for c in comps} == {"--opt-for-status", "--force"}
    assert ("status", "--git-completion-helper") in git_calls


def test_real_subcommands_skip_alias_lookup(git_calls, completion_context_parse):
    comps = completions_from_result(
        _complete(completion_context_parse, "git checkout -")
    )
    assert {str(c) for c in comps} == {"--opt-for-checkout", "--force"}
    assert _CONFIG_ARGS not in git_calls


def test_shell_alias_defers_and_is_never_executed(git_calls, completion_context_parse):
    """``--git-completion-helper`` on a ``!...`` alias would run the alias body."""
    assert _complete(completion_context_parse, "git sh -") is None
    assert ("sh", "--git-completion-helper") not in git_calls


@skip_if_not_has("git")
def test_aliases_with_real_git(tmp_path, monkeypatch, completion_context_parse):
    config = tmp_path / "gitconfig"
    config.write_text("[alias]\n    co = checkout\n    st = status\n    br = branch\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")

    comps = completions_from_result(_complete(completion_context_parse, "git "))
    by_value = {str(c): c for c in comps}
    assert {"co", "st", "br", "checkout", "status"} <= by_value.keys()
    assert by_value["co"].description == "checkout"
