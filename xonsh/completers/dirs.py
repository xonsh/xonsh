from xonsh.completers.man import complete_from_man
from xonsh.completers.path import complete_dir
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    CommandArg,
)


def complete_cd(prefix, line, start, end, ctx):
    """
    Completion for "cd", includes only valid directory names.
    """
    if start != 0 and line.split(" ")[0] == "cd":
        results, prefix = complete_dir(prefix, line, start, end, ctx, True)
        if len(results) == 0:
            raise StopIteration
        return results, prefix
    return set()


def complete_rmdir(prefix, line, start, end, ctx):
    """
    Completion for "rmdir", includes only valid directory names.
    """
    if start != 0 and line.split(" ")[0] == "rmdir":
        opts = {
            i
            for i in complete_from_man(
                CompletionContext(
                    CommandContext(args=(CommandArg("rmdir"),), arg_index=1, prefix="-")
                )
            )
            if i.startswith(prefix)
        }
        comps, lp = complete_dir(prefix, line, start, end, ctx, True)
        if len(comps) == 0 and len(opts) == 0:
            raise StopIteration
        return comps | opts, lp
    return set()
