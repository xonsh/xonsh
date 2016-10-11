"""Base completer for xonsh."""
import collections.abc as cabc

from xonsh.completers.path import complete_path
from xonsh.completers.python import complete_python
from xonsh.completers.commands import complete_command


def complete_base(prefix, line, start, end, ctx):
    """If the line is empty, complete based on valid commands, python names,
    and paths.  If we are completing the first argument, complete based on
    valid commands and python names.
    """
    if line.strip() == '':
        out = (complete_python(prefix, line, start, end, ctx) |
               complete_command(prefix, line, start, end, ctx))
        paths = complete_path(prefix, line, start, end, ctx, False)
        return (out | paths[0]), paths[1]
    elif prefix == line:
        python_comps = complete_python(prefix, line, start, end, ctx)
        if isinstance(python_comps, cabc.Sequence):
            return (python_comps[0] |
                    complete_command(prefix, line, start, end, ctx),
                    python_comps[1])
        else:
            return (python_comps |
                    complete_command(prefix, line, start, end, ctx))
    return set()
