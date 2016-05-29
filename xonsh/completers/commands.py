import builtins

from xonsh.completers.tools import get_filter_function

SKIP_TOKENS = {'sudo', 'time', 'timeit', 'which', 'showcmd'}


def complete_command(cmd, line, start, end, ctx):
    space = ' '
    return {s + space
            for s in builtins.__xonsh_commands_cache__
            if get_filter_function()(s, cmd)}


def complete_skipper(cmd, line, start, end, ctx):
    res = line.split(' ', 1)
    if len(res) == 2:
        first, rest = res
    else:
        first = res[0]
        rest = ''
    if first in SKIP_TOKENS:
        comp = builtins.__xonsh_shell__.shell.completer
        res = rest.split(' ', 1)
        if len(res) == 1:
            comp_func = complete_command
        else:
            comp_func = comp.complete
        return comp_func(cmd,
                         rest,
                         start - len(first) - 1,
                         end - len(first) - 1,
                         ctx)

    else:
        return set()
