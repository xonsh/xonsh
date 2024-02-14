"""Base completer for xonsh."""

import collections.abc as cabc

from xonsh.completers.commands import complete_command
from xonsh.completers.path import contextual_complete_path
from xonsh.completers.python import complete_python
from xonsh.completers.tools import apply_lprefix, contextual_completer
from xonsh.parsers.completion_context import CompletionContext


@contextual_completer
def complete_base(context: CompletionContext):
    """If the line is empty, complete based on valid commands, python names, and paths."""
    # If we are completing the first argument, complete based on
    # valid commands and python names.
    if context.command is None or context.command.arg_index != 0:
        # don't do unnecessary completions
        return

    # get and unpack python completions
    python_comps = complete_python(context) or set()
    if isinstance(python_comps, cabc.Sequence):
        python_comps, python_comps_len = python_comps  # type: ignore
        yield from apply_lprefix(python_comps, python_comps_len)
    else:
        yield from python_comps

    # add command completions
    yield from complete_command(context.command)

    # add paths, if needed
    if not context.command.prefix:
        path_comps, path_comp_len = contextual_complete_path(
            context.command, cdpath=False
        )
        yield from apply_lprefix(path_comps, path_comp_len)
