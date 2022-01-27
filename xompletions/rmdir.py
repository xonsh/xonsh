from xonsh.completers.path import complete_dir
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(ctx: CommandContext):
    """
    Completion for "rmdir", includes only valid directory names.
    """
    # if starts with the given prefix then it will get completions from man page
    if not ctx.prefix.startswith("-") and ctx.arg_index > 0:
        comps, lprefix = complete_dir(ctx)
        if not comps:
            raise StopIteration  # no further file completions
        return comps, lprefix
