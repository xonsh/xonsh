"""Base completer for xonsh."""

import collections.abc as cabc

from xonsh.completers.commands import complete_command
from xonsh.completers.path import contextual_complete_path
from xonsh.completers.python import complete_python
from xonsh.completers.tools import (
    RichCompletion,
    apply_lprefix,
    contextual_completer,
)
from xonsh.parsers.completion_context import CompletionContext


def _with_source(completions, source):
    for comp in completions:
        if isinstance(comp, RichCompletion):
            yield RichCompletion(
                str(comp),
                prefix_len=comp.prefix_len,
                display=comp.display,
                description=comp.description,
                style=comp.style,
                append_closing_quote=comp.append_closing_quote,
                append_space=comp.append_space,
                source=getattr(comp, "source", None) or source,
            )
        else:
            yield RichCompletion(
                str(comp),
                source=source,
            )

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
        yield from _with_source(
            apply_lprefix(python_comps, python_comps_len),
            "python",
        )
    else:
        yield from _with_source(python_comps, "python")

    # add command completions
    yield from complete_command(context.command)

    # add paths, if needed
    if not context.command.prefix:
        path_comps, path_comp_len = contextual_complete_path(
            context.command, cdpath=False
        )
        yield from _with_source(
            apply_lprefix(path_comps, path_comp_len),
            "path",
        )
