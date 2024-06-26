from xonsh.built_ins import XSH
from xonsh.completers.completer import (
    add_one_completer,
    remove_completer,
)
from xonsh.completers.tools import contextual_command_completer
from xonsh.parsers.completion_context import CommandContext

# for backward compatibility
_add_one_completer = add_one_completer


def _remove_completer(args):
    """for backward compatibility"""
    return remove_completer(args[0])


@contextual_command_completer
def complete_aliases(command: CommandContext):
    """Complete any alias that has ``xonsh_complete`` attribute.

    The said attribute should be a function. The current command context is passed to it.
    """

    if not command.args:
        return
    cmd = command.args[0].value

    if cmd not in XSH.aliases:
        # only complete aliases
        return
    alias = XSH.aliases.get(cmd)  # type: ignore

    completer = getattr(alias, "xonsh_complete", None)
    if not completer:
        return

    if command.suffix:
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return

    possible = completer(command=command, alias=alias)
    return possible, False
