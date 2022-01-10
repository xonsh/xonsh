from xonsh.completers.path import complete_dir
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(command: CommandContext):
    """
    Completion for "cd", includes only valid directory names.
    """
    results, lprefix = complete_dir(command)
    if len(results) == 0:
        raise StopIteration
    return results, lprefix
