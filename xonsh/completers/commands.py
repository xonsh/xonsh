import os
import builtins

from xonsh.tools import executables_in
from xonsh.platform import ON_WINDOWS
from xonsh.completers.tools import get_filter_function

SKIP_TOKENS = {'sudo', 'time', 'timeit', 'which', 'showcmd', 'man'}


def complete_command(cmd, line, start, end, ctx):
    """
    Returns a list of valid commands starting with the first argument
    """
    space = ' '
    out = {s + space
           for s in builtins.__xonsh_commands_cache__
           if get_filter_function()(s, cmd)}
    if ON_WINDOWS:
        out |= {i
                for i in executables_in('.')
                if i.startswith(cmd)}
    base = os.path.basename(cmd)
    if os.path.isdir(base):
        out |= {os.path.join(base, i)
                for i in executables_in(base)
                if i.startswith(cmd)}
    return out


def complete_skipper(cmd, line, start, end, ctx):
    """
    Skip over several tokens (e.g., sudo) and complete based on the rest of the
    line.
    """
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
