"""Completers for pip."""

from xonsh.completers.tools import comp_based_completer
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(ctx: CommandContext):
    """Completes python's package manager pip."""

    return comp_based_completer(ctx, PIP_AUTO_COMPLETE="1")
