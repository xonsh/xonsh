"""Completers for ``python -m <module>`` commands."""

import os

from xonsh.completers.tools import complete_from_sub_proc
from xonsh.parsers.completion_context import CommandArg, CommandContext


def _complete_pip(ctx, module_arg_index):
    """Delegate to pip's completer."""
    from xompletions import pip as _pip

    args = (CommandArg("pip"),) + ctx.args[module_arg_index + 1 :]
    pip_ctx = ctx._replace(args=args, arg_index=ctx.arg_index - module_arg_index)
    return _pip.xonsh_complete(pip_ctx)


def _complete_argcomplete(ctx, module_arg_index):
    """Complete using argcomplete protocol (pytest, pipx, nox, etc.)."""
    module_name = ctx.args[module_arg_index].value
    # Build COMP_LINE as if the module is the command
    line_parts = [arg.value for arg in ctx.args[module_arg_index:]]
    if ctx.prefix:
        line_parts.append(ctx.prefix)
    comp_line = " ".join(line_parts)
    if not ctx.prefix:
        comp_line += " "

    return complete_from_sub_proc(
        ctx.args[0].value,
        "-m",
        module_name,
        _ARGCOMPLETE="1",
        _ARGCOMPLETE_IFS="\n",
        _ARGCOMPLETE_OUTPUT_FD="1",
        COMP_LINE=comp_line,
        COMP_POINT=str(len(comp_line)),
    )


# Map module names to their completer functions.
# Extend from xonshrc: ``from xompletions.python import MODULE_COMPLETERS``
#
# Available helpers:
#   _complete_pip          — pip's PIP_AUTO_COMPLETE protocol
#   _complete_argcomplete  — argcomplete protocol (_ARGCOMPLETE=1, output to stdout)
MODULE_COMPLETERS = {
    "pip": _complete_pip,
}


def xonsh_complete(ctx: CommandContext):
    """Completes ``python -m <module>`` by delegating to the module's completer."""

    if (
        len(ctx.args) >= 3
        and os.path.basename(ctx.args[0].value).startswith("python")
        and ctx.args[1].value == "-m"
        and ctx.arg_index >= 3
    ):
        module_name = ctx.args[2].value
        completer = MODULE_COMPLETERS.get(module_name)
        if completer:
            return completer(ctx, module_arg_index=2)
    return None
