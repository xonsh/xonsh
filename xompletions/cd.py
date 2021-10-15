from xonsh.completers.path import complete_dir
from xonsh.completers.tools import contextual_command_completer_for
from xonsh.parsers.completion_context import CommandContext


@contextual_command_completer_for("cd")
def complete_cd(command: CommandContext):
    """
    Completion for "cd", includes only valid directory names.
    """
    results, lprefix = complete_dir(command)
    if len(results) == 0:
        raise StopIteration
    return results, lprefix
