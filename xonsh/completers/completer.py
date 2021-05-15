import collections
from xonsh.parsers.completion_context import CommandContext

from xonsh.built_ins import XSH
from xonsh.completers.tools import contextual_command_completer_for, justify


@contextual_command_completer_for("completer")
def complete_completer(command: CommandContext):
    """
    Completion for "completer"
    """
    if command.suffix:
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return None

    curix = command.arg_index

    compnames = set(XSH.completers.keys())
    if curix == 1:
        possible = {"list", "help", "add", "remove"}
    elif curix == 2:
        first_arg = command.args[1].value
        if first_arg == "help":
            possible = {"list", "add", "remove"}
        elif first_arg == "remove":
            possible = compnames
        else:
            raise StopIteration
    else:
        if command.args[1].value != "add":
            raise StopIteration
        if curix == 3:
            possible = {i for i, j in XSH.ctx.items() if callable(j)}
        elif curix == 4:
            possible = (
                {"start", "end"}
                | {">" + n for n in compnames}
                | {"<" + n for n in compnames}
            )
        else:
            raise StopIteration
    return {i for i in possible if i.startswith(command.prefix)}


def add_one_completer(name, func, loc="end"):
    new = collections.OrderedDict()
    if loc == "start":
        new[name] = func
        for (k, v) in XSH.completers.items():
            new[k] = v
    elif loc == "end":
        for (k, v) in XSH.completers.items():
            new[k] = v
        new[name] = func
    else:
        direction, rel = loc[0], loc[1:]
        found = False
        for (k, v) in XSH.completers.items():
            if rel == k and direction == "<":
                new[name] = func
                found = True
            new[k] = v
            if rel == k and direction == ">":
                new[name] = func
                found = True
        if not found:
            new[name] = func
    XSH.completers.clear()
    XSH.completers.update(new)


def list_completers():
    """List the active completers"""
    o = "Registered Completer Functions: \n"
    _comp = XSH.completers
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
    if name not in XSH.completers:
        err = f"The name {name} is not a registered completer function."
    if err is None:
        del XSH.completers[name]
        return
    else:
        return None, err + "\n", 1
