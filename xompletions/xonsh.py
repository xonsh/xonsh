from xonsh.cli_utils import ArgparseCompleter

from xonsh.completers.tools import get_filter_function
from xonsh.parsers.completion_context import CommandContext


def xonsh_complete(command: CommandContext):
    """Completer for ``xonsh`` command using its ``argparser``"""

    from xonsh.main import parser

    completer = ArgparseCompleter(parser, command=command)
    fltr = get_filter_function()
    for comp in completer.complete():
        if fltr(comp, command.prefix):
            yield comp
    # todo: part of return value will have unfiltered=False/True. based on that we can use fuzzy to rank the results
