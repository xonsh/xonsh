from xonsh.completers.man import complete_from_man
from xonsh.completers.path import complete_dir
from xonsh.completers.tools import contextual_command_completer_for
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
)


@contextual_command_completer_for("cd")
def complete_cd(command: CommandContext):
    """
    Completion for "cd", includes only valid directory names.
    """
    results, lprefix = complete_dir(command)
    if len(results) == 0:
        raise StopIteration
    return results, lprefix


@contextual_command_completer_for("rmdir")
def complete_rmdir(command: CommandContext):
    """
    Completion for "rmdir", includes only valid directory names.
    """
    opts = complete_from_man(CompletionContext(command))
    comps, lp = complete_dir(command)
    if len(comps) == 0 and len(opts) == 0:
        raise StopIteration
    return comps | opts, lp
