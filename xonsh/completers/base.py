"""Base completer for xonsh."""
import typing as tp
import collections.abc as cabc
from xonsh.parsers.completion_context import CompletionContext
from xonsh.completers.tools import (
    contextual_completer,
    Completion,
    apply_lprefix,
)

from xonsh.completers.path import contextual_complete_path
from xonsh.completers.python import complete_python
from xonsh.completers.commands import complete_command


@contextual_completer
def complete_base(context: CompletionContext):
    """If the line is empty, complete based on valid commands, python names, and paths."""
    # If we are completing the first argument, complete based on
    # valid commands and python names.
    out: tp.Set[Completion] = set()
    if context.command is None or context.command.arg_index != 0:
        # don't do unnecessary completions
        return out

    # get and unpack python completions
    python_comps = complete_python(context) or set()
    if isinstance(python_comps, cabc.Sequence):
        python_comps, python_comps_len = python_comps  # type: ignore
        out.update(apply_lprefix(python_comps, python_comps_len))
    else:
        out.update(python_comps)

    # add command completions
    out.update(complete_command(context.command))

    # add paths, if needed
    if not context.command.prefix:
        path_comps, path_comp_len = contextual_complete_path(
            context.command, cdpath=False
        )
        out.update(apply_lprefix(path_comps, path_comp_len))

    return out
