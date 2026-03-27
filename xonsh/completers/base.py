"""Base completer for xonsh."""

import collections.abc as cabc

from xonsh.built_ins import XSH
from xonsh.completers.commands import complete_command
from xonsh.completers.path import contextual_complete_path
from xonsh.completers.python import complete_python
from xonsh.completers.tools import apply_lprefix, contextual_completer
from xonsh.parsers.completion_context import CompletionContext

# Mapping from completion str value to sub-source name, used by XONSH_TRACE_COMPLETIONS.
_trace_sources: dict[str, str] = {}


def _tag(completions, source):
    """Record trace source for each completion without mutating the object."""
    for c in completions:
        comp = c[0] if isinstance(c, tuple) else c
        _trace_sources[str(comp)] = source
        yield c


@contextual_completer
def complete_base(context: CompletionContext):
    """If the line is empty, complete based on valid commands, python names, and paths."""
    # If we are completing the first argument, complete based on
    # valid commands and python names.
    if context.command is None or context.command.arg_index != 0:
        # don't do unnecessary completions
        return

    trace = (XSH.env or {}).get("XONSH_TRACE_COMPLETIONS", False)
    if trace:
        _trace_sources.clear()

    # get and unpack python completions
    python_comps = complete_python(context) or set()
    if isinstance(python_comps, cabc.Sequence):
        python_comps, python_comps_len = python_comps  # type: ignore
        comps = list(apply_lprefix(python_comps, python_comps_len))
    else:
        comps = list(python_comps)
    yield from (_tag(comps, "base:python") if trace else comps)

    # add command completions
    cmd_comps = list(complete_command(context.command))
    yield from (_tag(cmd_comps, "base:command") if trace else cmd_comps)

    # add paths, if needed
    if not context.command.prefix:
        path_comps, path_comp_len = contextual_complete_path(
            context.command, cdpath=False
        )
        p_comps = list(apply_lprefix(path_comps, path_comp_len))
        yield from (_tag(p_comps, "base:path") if trace else p_comps)
