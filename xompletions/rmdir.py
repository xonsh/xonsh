from xonsh.completers.man import complete_from_man
from xonsh.completers.path import complete_dir
from xonsh.parsers.completion_context import CompletionContext, CommandContext


def xonsh_complete(command: CommandContext):
    """
    Completion for "rmdir", includes only valid directory names.
    """
    opts = complete_from_man(CompletionContext(command))
    comps, lp = complete_dir(command)
    if len(comps) == 0 and len(opts) == 0:
        raise StopIteration
    return comps | opts, lp
