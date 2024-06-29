from xonsh.cli_utils import ArgparseCompleter
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(command: CommandContext):
    """Completer for ``xonsh`` command using its ``argparser``"""

    from xonsh.main import parser

    completer = ArgparseCompleter(parser, command=command)
    return completer.complete(), False
