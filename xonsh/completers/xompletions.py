"""Provides completions for xonsh internal utilities"""

from xonsh.parsers.completion_context import CommandContext
import xonsh.xontribs as xx
import xonsh.xontribs_meta as xmt
import xonsh.tools as xt
from xonsh.xonfig import XONFIG_MAIN_ACTIONS
from xonsh.completers.tools import contextual_command_completer_for


@contextual_command_completer_for("xonfig")
def complete_xonfig(command: CommandContext):
    """Completion for ``xonfig``"""
    curix = command.arg_index
    if curix == 1:
        possible = set(XONFIG_MAIN_ACTIONS.keys()) | {"-h"}
    elif curix == 2 and command.args[1].value == "colors":
        possible = set(xt.color_style_names())
    else:
        raise StopIteration
    return {i for i in possible if i.startswith(command.prefix)}


def _list_installed_xontribs():
    meta = xmt.get_xontribs()
    installed = []
    for name in meta:
        spec = xx.find_xontrib(name)
        if spec is not None:
            installed.append(spec.name.rsplit(".")[-1])

    return installed


@contextual_command_completer_for("xontrib")
def complete_xontrib(command: CommandContext):
    """Completion for ``xontrib``"""
    curix = command.arg_index
    if curix == 1:
        possible = {"list", "load"}
    elif curix == 2 and command.args[1].value == "load":
        possible = _list_installed_xontribs()
    else:
        raise StopIteration

    return {i for i in possible if i.startswith(command.prefix)}
