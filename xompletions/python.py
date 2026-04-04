"""Completers for commands invoked via ``python -m <module>``."""

import os

from xompletions import pip as _pip_completer
from xonsh.parsers.completion_context import CommandArg, CommandContext


def xonsh_complete(ctx: CommandContext):
    """Completes ``python -m pip`` by delegating to pip's completer."""

    # Only handle: python -m pip ...
    if (
        len(ctx.args) >= 3
        and os.path.basename(ctx.args[0].value).startswith("python")
        and ctx.args[1].value == "-m"
        and ctx.args[2].value == "pip"
        and ctx.arg_index >= 3
    ):
        # Rewrite context as if the command is just "pip ..."
        args = (CommandArg("pip"),) + ctx.args[3:]
        pip_ctx = ctx._replace(args=args, arg_index=ctx.arg_index - 2)
        return _pip_completer.xonsh_complete(pip_ctx)
    return None
