"""Completers for vox."""
# pylint: disable=invalid-name, missing-docstring, unsupported-membership-test
# pylint: disable=unused-argument, not-an-iterable
from xonsh.completers.tools import (
    contextual_command_completer,
    get_filter_function,
    RichCompletion,
)
from xonsh.parsers.completion_context import CommandContext
import xontrib.voxapi as voxapi


VOX_LIST_COMMANDS = {"activate", "workon", "enter", "remove", "rm", "delete", "del"}
VOX_ALL_COMMANDS = {
    "new",
    "create",
    "activate",
    "workon",
    "enter",
    "deactivate",
    "exit",
    "list",
    "ls",
    "remove",
    "rm",
    "delete",
    "del",
}


@contextual_command_completer
def complete_vox(context: CommandContext):
    """Completes xonsh's vox command"""
    prefix = context.prefix
    if context.arg_index == 0 or (not context.args[0].value == "vox"):
        return None
    filter_func = get_filter_function()

    if context.arg_index == 2 and context.args[1].value in VOX_LIST_COMMANDS:
        return set(voxapi.Vox().keys())

    if context.arg_index == 1:
        suggestions = {
            RichCompletion(c, append_space=True)
            for c in VOX_ALL_COMMANDS
            if filter_func(c, prefix)
        }
        return suggestions

    return None
