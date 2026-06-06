"""Git completer: subcommands, aliases, options, and refs."""

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


def _get_aliases() -> "dict[str, str]":
    """Configured git aliases mapped to their bodies (``co`` → ``checkout``).

    ``-z`` NUL-terminates entries so multi-line alias bodies stay
    parseable; within an entry the key is separated from the value by
    the first newline.
    """
    out = _run_git("config", "-z", "--get-regexp", r"^alias\.")
    if out is None:
        return {}
    aliases = {}
    for entry in out.split("\0"):
        name, _, body = entry.partition("\n")
        if name.startswith("alias."):
            aliases[name.removeprefix("alias.")] = body.replace("\n", " ")
    return aliases


def xonsh_complete(context: CommandContext):
    """Complete git subcommands, aliases, options, and branch/tag refs."""
    if context.arg_index == 0:
        return

    # git <subcmd><Tab> — the ``alias`` group lists user-configured
    # aliases (``co = checkout``) next to the subcommands; the alias
    # body is shown as the completion description.
    if context.arg_index == 1:
        out = _run_git("--list-cmds=main,others,alias")
        if out is None:
            return
        aliases = _get_aliases()
        return {
            RichCompletion(s, append_space=True, description=aliases.get(s, ""))
            for s in out.split()
        }, False

    subcmd = context.args[1].value

    # Resolve a configured alias (``co`` → ``checkout``) so option and
    # ref completion work for aliases too. Subcommands already known to
    # take refs skip the lookup — git ignores aliases that shadow real
    # commands. A shell alias (``!...``) has no git subcommand to
    # resolve to and must never reach ``--git-completion-helper`` below
    # (git would *execute* the alias body), so defer to the next
    # completer.
    if subcmd not in _REF_SUBCMDS:
        alias_body = _get_aliases().get(subcmd)
        if alias_body is not None:
            if alias_body.startswith("!"):
                return
            body_words = alias_body.split()
            if body_words:
                subcmd = body_words[0]

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
