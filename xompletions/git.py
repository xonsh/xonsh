"""Git completer: subcommands, options, and refs."""

import subprocess

from xonsh.completers.tools import RichCompletion
from xonsh.parsers.completion_context import CommandContext

_REF_SUBCMDS = frozenset(
    {
        "checkout",
        "switch",
        "merge",
        "rebase",
        "branch",
        "cherry-pick",
        "log",
        "diff",
        "show",
        "reset",
        "push",
        "pull",
        "fetch",
        "stash",
        "bisect",
        "blame",
        "revert",
        "tag",
    }
)


def _run_git(*args) -> "str | None":
    try:
        return subprocess.check_output(
            ["git", *args],
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        if err:
            from xonsh.tools import print_above_prompt

            print_above_prompt(f"completer git: {err}")
        return None
    except (OSError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def xonsh_complete(context: CommandContext):
    """Complete git subcommands, options, and branch/tag refs."""
    if context.arg_index == 0:
        return

    # git <subcmd><Tab>
    if context.arg_index == 1:
        out = _run_git("--list-cmds=main,others")
        if out is None:
            return
        return {RichCompletion(s, append_space=True) for s in out.split()}, False

    subcmd = context.args[1].value

    # git <subcmd> -<Tab>
    if context.prefix.startswith("-"):
        out = _run_git(subcmd, "--git-completion-helper")
        if out is None:
            return
        return {RichCompletion(o) for o in out.split() if o.startswith("-")}, False

    # git <subcmd> <ref><Tab>
    if subcmd in _REF_SUBCMDS:
        out = _run_git(
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/",
            "refs/tags/",
            "refs/remotes/",
        )
        if out is None:
            return
        return {RichCompletion(r, append_space=True) for r in out.split()}, False
