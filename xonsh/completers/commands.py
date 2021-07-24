import os
import typing as tp

import xonsh.tools as xt
import xonsh.platform as xp
from xonsh.completer import Completer
from xonsh.completers.tools import (
    get_filter_function,
    contextual_command_completer,
    RichCompletion,
    Completion,
    non_exclusive_completer,
)
from xonsh.parsers.completion_context import CompletionContext, CommandContext
from xonsh.built_ins import XSH


SKIP_TOKENS = {"sudo", "time", "timeit", "which", "showcmd", "man"}
END_PROC_TOKENS = ("|", ";", "&&")  # includes ||
END_PROC_KEYWORDS = {"and", "or"}


def complete_command(command: CommandContext):
    """
    Returns a list of valid commands starting with the first argument
    """
    cmd = command.prefix
    out: tp.Set[Completion] = {
        RichCompletion(s, append_space=True)
        for s in XSH.commands_cache  # type: ignore
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
    """

    # Contextual completers don't need us to skip tokens since they get the correct completion context -
    # meaning we only need to skip commands like ``sudo``.
    skip_part_num = 0
    # all the args before the current argument
    for arg in command_context.args[: command_context.arg_index]:
        if arg.value not in SKIP_TOKENS:
            break
        skip_part_num += 1

    if skip_part_num == 0:
        return None

    skipped_command_context = command_context._replace(
        args=command_context.args[skip_part_num:],
        arg_index=command_context.arg_index - skip_part_num,
    )

    if skipped_command_context.arg_index == 0:
        # completing the command after a SKIP_TOKEN
        return complete_command(skipped_command_context)

    completer: Completer = XSH.shell.shell.completer  # type: ignore
    return completer.complete_from_context(CompletionContext(skipped_command_context))


@non_exclusive_completer
@contextual_command_completer
def complete_end_proc_tokens(command_context: CommandContext):
    """If there's no space following '|', '&', or ';' - insert one."""
    if command_context.opening_quote or not command_context.prefix:
        return None
    prefix = command_context.prefix
    # for example `echo a|`, `echo a&&`, `echo a ;`
    if any(prefix.endswith(ending) for ending in END_PROC_TOKENS):
        return {RichCompletion(prefix, append_space=True)}
    return None


@non_exclusive_completer
@contextual_command_completer
def complete_end_proc_keywords(command_context: CommandContext):
    """If there's no space following 'and' or 'or' - insert one."""
    if command_context.opening_quote or not command_context.prefix:
        return None
    prefix = command_context.prefix
    if prefix in END_PROC_KEYWORDS:
        return {RichCompletion(prefix, append_space=True)}
    return None
