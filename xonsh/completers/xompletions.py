"""Provides completions for xonsh internal utilities"""

import xonsh.xontribs as xx
import xonsh.tools as xt


def complete_xonfig(prefix, line, start, end, ctx):
    """Completion for ``xonfig``"""
    args = line.split(" ")
    if len(args) == 0 or args[0] != "xonfig":
        return None
    curix = args.index(prefix)
    if curix == 1:
        possible = {"info", "wizard", "styles", "colors", "-h"}
    elif curix == 2 and args[1] == "colors":
        possible = set(xt.color_style_names())
    else:
        raise StopIteration
    return {i for i in possible if i.startswith(prefix)}


def _list_installed_xontribs():
    meta = xx.xontrib_metadata()
    installed = []
    for md in meta["xontribs"]:
        name = md["name"]
        spec = xx.find_xontrib(name)
        if spec is not None:
            installed.append(spec.name.rsplit(".")[-1])

    return installed


def complete_xontrib(prefix, line, start, end, ctx):
    """Completion for ``xontrib``"""
    args = line.split(" ")
    if len(args) == 0 or args[0] != "xontrib":
        return None
    curix = args.index(prefix)
    if curix == 1:
        possible = {"list", "load"}
    elif curix == 2:
        if args[1] == "load":
            possible = _list_installed_xontribs()
    else:
        raise StopIteration

    return {i for i in possible if i.startswith(prefix)}
