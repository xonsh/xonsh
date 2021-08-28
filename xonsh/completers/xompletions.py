"""Provides completions for xonsh internal utilities"""

import xonsh.xontribs as xx
import xonsh.xontribs_meta as xmt
from xonsh.completers.tools import contextual_command_completer_for
from xonsh.parsers.completion_context import CommandContext


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
    """Completion for ``xontrib``."""
    curix = command.arg_index
    if curix == 1:
        possible = {"list", "load"}
    elif curix == 2 and command.args[1].value == "load":
        possible = _list_installed_xontribs()
    else:
        raise StopIteration

    return {i for i in possible if i.startswith(command.prefix)}
