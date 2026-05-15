"""Completer for ``sudo``.

``sudo`` is more than a transparent command wrapper: it has its own flag
grammar, accepts ``VAR=value`` environment assignments before the command,
and honours the POSIX ``--`` end-of-options sentinel. The generic
command-token skipper in :mod:`xonsh.completers.commands` only knows how to
strip the literal ``sudo`` token, which leaves ``sudo -- foo``,
``sudo -u root foo`` and similar invocations without useful completions.

This module walks ``ctx.args`` past every token that belongs to ``sudo``'s
own prefix (flags, their values, ``VAR=value`` assignments, ``--``) and
then either offers command names (when the cursor sits on the inner
command word) or re-enters the full completion pipeline with the inner
command at ``args[0]`` so the inner command's own completers
(``man``, paths, ``pip``'s xompletion, …) surface.
"""

import re

from xonsh.built_ins import XSH
from xonsh.completers.commands import complete_command
from xonsh.parsers.completion_context import CommandContext, CompletionContext

# Short-form sudo flags whose next argument is the flag's value
# (``sudo -u root cmd``). Long-form variants are tracked separately below
# because they can also appear as ``--user=root`` in a single token.
_SUDO_OPTS_WITH_ARG = frozenset(
    {"-C", "-D", "-R", "-T", "-U", "-c", "-g", "-h", "-p", "-r", "-t", "-u"}
)

# Long-form sudo flags whose next argument is the flag's value when used
# without an embedded ``=`` (``--user root`` vs ``--user=root``).
_SUDO_LONG_OPTS_WITH_ARG = frozenset(
    {
        "--chdir",
        "--chroot",
        "--class",
        "--close-from",
        "--command-timeout",
        "--group",
        "--host",
        "--other-user",
        "--prompt",
        "--role",
        "--type",
        "--user",
    }
)

# ``VAR=value`` env-var assignments that sudo accepts before the command.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _find_inner_command_position(args) -> int:
    """Return the index in ``args`` where the inner command begins.

    Walks past ``sudo`` itself, every flag (consuming the next token when
    the flag is known to take a value), every ``VAR=value`` env-var
    assignment, and the ``--`` end-of-options sentinel. Stops at the first
    bare positional — that's the inner command. The return value can be
    greater than ``len(args)`` when a value-taking flag (``-u``,
    ``--user``) sits at the end without its value yet typed; callers
    interpret that as "the inner command hasn't been reached".
    """
    i = 1  # skip ``sudo`` itself
    while i < len(args):
        v = args[i].value
        if v == "--":
            return i + 1
        if v.startswith("-"):
            # ``--user=root`` carries its value inside the same token.
            if v.startswith("--") and "=" in v:
                i += 1
            elif v in _SUDO_OPTS_WITH_ARG or v in _SUDO_LONG_OPTS_WITH_ARG:
                # Flag consumes the next arg as its value.
                i += 2
            else:
                # Unknown / value-less flag (``-E``, ``-H``, …).
                i += 1
            continue
        if _ENV_ASSIGN_RE.match(v):
            i += 1
            continue
        return i
    return i


def xonsh_complete(ctx: CommandContext):
    """Complete arguments to ``sudo``."""
    inner = _find_inner_command_position(ctx.args)

    if ctx.arg_index < inner:
        # Cursor sits on the value-slot of a sudo flag (``sudo -u <Tab>``)
        # or some other token that still belongs to sudo's own prefix.
        # Defer to the rest of the completer pipeline.
        return None

    if ctx.arg_index == inner:
        # Cursor is on the inner-command slot. A ``-`` prefix here means
        # the user is still typing one of sudo's own flags (e.g.
        # ``sudo -E -<Tab>``) — defer to the man-page completer instead
        # of returning command names that start with ``-``.
        if ctx.prefix.startswith("-"):
            return None
        return complete_command(ctx)

    # Cursor is past the inner command's name, inside its own arguments.
    # Re-enter the completer pipeline with the inner command at args[0]
    # so its completers (paths, man flags, xompletions, …) fire.
    skipped = ctx._replace(
        args=ctx.args[inner:],
        arg_index=ctx.arg_index - inner,
    )
    completer = XSH.shell.shell.completer  # type: ignore[union-attr]
    return completer.complete_from_context(CompletionContext(skipped))
