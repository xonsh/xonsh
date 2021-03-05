import os
import builtins
import typing as tp

import xonsh.tools as xt
import xonsh.platform as xp
from xonsh.completers.tools import (
    get_filter_function,
    contextual_command_completer,
    is_contextual_completer,
    RichCompletion,
    Completion,
)
from xonsh.parsers.completion_context import CompletionContext, CommandContext

SKIP_TOKENS = {"sudo", "time", "timeit", "which", "showcmd", "man"}
END_PROC_TOKENS = {"|", "||", "&&", "and", "or"}


def complete_command(command: CommandContext):
    """
    Returns a list of valid commands starting with the first argument
    """
    cmd = command.prefix
    out: tp.Set[Completion] = {
        RichCompletion(s, append_space=True)
        for s in builtins.__xonsh__.commands_cache  # type: ignore
        if get_filter_function()(s, cmd)
    }
    if xp.ON_WINDOWS:
        out |= {i for i in xt.executables_in(".") if i.startswith(cmd)}
    base = os.path.basename(cmd)
    if os.path.isdir(base):
        out |= {
            os.path.join(base, i) for i in xt.executables_in(base) if i.startswith(cmd)
        }
    return out


@contextual_command_completer
def complete_skipper(command_context: CommandContext):
    """
    Skip over several tokens (e.g., sudo) and complete based on the rest of the command.

    Contextual completers don't need us to skip tokens since they get the correct completion context -
    meaning we only need to skip commands like ``sudo``.
    """
    skip_part_num = 0
    for skip_part_num, arg in enumerate(
        command_context.args[: command_context.arg_index]
    ):
        # all the args before the current argument
        if arg.value not in SKIP_TOKENS:
            break

    if skip_part_num == 0:
        return None

    skipped_context = CompletionContext(
        command=command_context._replace(
            args=command_context.args[skip_part_num:],
            arg_index=command_context.arg_index - skip_part_num,
        )
    )

    completers = builtins.__xonsh__.completers.values()  # type: ignore
    for completer in completers:
        if is_contextual_completer(completer):
            results = completer(skipped_context)
            if results:
                return results
    return None


def complete_end_proc_tokens(cmd, line, start, end, ctx):
    """If there's no space following an END_PROC_TOKEN, insert one"""
    if cmd in END_PROC_TOKENS and line[end : end + 1] != " ":
        return {RichCompletion(cmd, append_space=True)}
