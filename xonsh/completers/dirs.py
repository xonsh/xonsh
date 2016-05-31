import os

from xonsh.completers.path import complete_dir

PREVENT_OTHERS = ['path']


def complete_cd(prefix, line, start, end, ctx):
    if start != 0 and line.split(' ')[0] == 'cd':
        return complete_dir(prefix, line, start, end, ctx)
    return set()


def complete_rmdir(prefix, line, start, end, ctx):
    if start != 0 and line.split(' ')[0] == 'rmdir':
        return complete_dir(prefix, line, start, end, ctx)
    return set()
