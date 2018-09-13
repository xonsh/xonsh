from xonsh.completers.man import complete_from_man
from xonsh.completers.path import complete_dir


def complete_cd(prefix, line, start, end, ctx):
    """
    Completion for "cd", includes only valid directory names.
    """
    if start != 0 and line.split(" ")[0] == "cd":
        return complete_dir(prefix, line, start, end, ctx, True)
    return set()


def complete_rmdir(prefix, line, start, end, ctx):
    """
    Completion for "rmdir", includes only valid directory names.
    """
    if start != 0 and line.split(" ")[0] == "rmdir":
        opts = {
            i
            for i in complete_from_man("-", "rmdir -", 6, 7, ctx)
            if i.startswith(prefix)
        }
        comps, lp = complete_dir(prefix, line, start, end, ctx, True)
        return comps | opts, lp
    return set()
