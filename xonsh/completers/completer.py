import builtins
import collections
from xonsh.built_ins import current_xonsh_session
from xonsh.completers.tools import justify


def complete_completer(prefix, line, start, end, ctx):
    """
    Completion for "completer"
    """
    args = line.split(" ")
    if len(args) == 0 or args[0] != "completer":
        return None

    if end < len(line) and line[end] != " ":
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return None

    curix = args.index(prefix)

    compnames = set(builtins.__xonsh__.completers.keys())
    if curix == 1:
        possible = {"list", "help", "add", "remove"}
    elif curix == 2:
        if args[1] == "help":
            possible = {"list", "add", "remove"}
        elif args[1] == "remove":
            possible = compnames
        else:
            raise StopIteration
    else:
        if args[1] != "add":
            raise StopIteration
        if curix == 3:
            possible = {i for i, j in builtins.__xonsh__.ctx.items() if callable(j)}
        elif curix == 4:
            possible = (
                {"start", "end"}
                | {">" + n for n in compnames}
                | {"<" + n for n in compnames}
            )
        else:
            raise StopIteration
    return {i for i in possible if i.startswith(prefix)}


def add_one_completer(name, func, loc="end"):
    new = collections.OrderedDict()
    if loc == "start":
        new[name] = func
        for (k, v) in builtins.__xonsh__.completers.items():
            new[k] = v
    elif loc == "end":
        for (k, v) in builtins.__xonsh__.completers.items():
            new[k] = v
        new[name] = func
    else:
        direction, rel = loc[0], loc[1:]
        found = False
        for (k, v) in builtins.__xonsh__.completers.items():
            if rel == k and direction == "<":
                new[name] = func
                found = True
            new[k] = v
            if rel == k and direction == ">":
                new[name] = func
                found = True
        if not found:
            new[name] = func
    builtins.__xonsh__.completers.clear()
    builtins.__xonsh__.completers.update(new)


def list_completers():
    """List the active completers"""
    o = "Registered Completer Functions: \n"
    _comp = builtins.__xonsh__.completers
    ml = max((len(i) for i in _comp), default=0)
    _strs = []
    for c in _comp:
        if _comp[c].__doc__ is None:
            doc = "No description provided"
        else:
            doc = " ".join(_comp[c].__doc__.split())
        doc = justify(doc, 80, ml + 3)
        _strs.append("{: >{}} : {}".format(c, ml, doc))
    return o + "\n".join(_strs) + "\n"


def remove_completer(name: str):
    """removes a completer from xonsh

    Parameters
    ----------
    name:
        NAME is a unique name of a completer (run "completer list" to see the current
        completers in order)
    """
    err = None
    if name not in current_xonsh_session.completers:
        err = "The name %s is not a registered " "completer function." % name
    if err is None:
        del current_xonsh_session.completers[name]
        return
    else:
        return None, err + "\n", 1
