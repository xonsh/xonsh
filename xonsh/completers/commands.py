import os
import builtins

import xonsh.tools as xt
import xonsh.platform as xp

from xonsh.completers.tools import get_filter_function

SKIP_TOKENS = {'sudo', 'time', 'timeit', 'which', 'showcmd', 'man'}
END_PROC_TOKENS = {'|', '||', '&&', 'and', 'or'}


def complete_command(cmd, line, start, end, ctx):
    """
    Returns a list of valid commands starting with the first argument
    """
    space = ' '
    out = {s + space
           for s in builtins.__xonsh_commands_cache__
           if get_filter_function()(s, cmd)}
    if xp.ON_WINDOWS:
        out |= {i for i in xt.executables_in('.')
                if i.startswith(cmd)}
    base = os.path.basename(cmd)
    if os.path.isdir(base):
        out |= {os.path.join(base, i)
                for i in xt.executables_in(base)
                if i.startswith(cmd)}
    return out


def complete_skipper(cmd, line, start, end, ctx):
    """
    Skip over several tokens (e.g., sudo) and complete based on the rest of the
    line.
    """
    parts = line.split(' ')
    skip_part_num = 0
    for i, s in enumerate(parts):
        if s in END_PROC_TOKENS:
            skip_part_num = i + 1
    while len(parts) > skip_part_num:
        if parts[skip_part_num] not in SKIP_TOKENS:
            break
        skip_part_num += 1

    if skip_part_num == 0:
        return set()

    if len(parts) == skip_part_num + 1:
        comp_func = complete_command
    else:
        comp = builtins.__xonsh_shell__.shell.completer
        comp_func = comp.complete

    skip_len = len(' '.join(line[:skip_part_num])) + 1
    return comp_func(cmd,
                     ' '.join(parts[skip_part_num:]),
                     start - skip_len,
                     end - skip_len,
                     ctx)
