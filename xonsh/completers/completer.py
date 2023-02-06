import collections

from xonsh.built_ins import XSH
from xonsh.cli_utils import Annotated, Arg, NumpyDoc
from xonsh.completers.tools import RichCompletion, is_exclusive_completer, justify


def add_one_completer(name, func, loc="end"):
    new = collections.OrderedDict()
    if loc == "start":
        # Add new completer before the first exclusive one.
        # We don't want new completers to be before the non-exclusive ones,
        # because then they won't be used when this completer is successful.
        # On the other hand, if the new completer is non-exclusive,
        # we want it to be before all other exclusive completers so that is will always work.
        items = list(XSH.completers.items())
        first_exclusive = next(
            (i for i, (_, v) in enumerate(items) if is_exclusive_completer(v)),
            len(items),
        )
        for k, v in items[:first_exclusive]:
            new[k] = v
        new[name] = func
        for k, v in items[first_exclusive:]:
            new[k] = v
    elif loc == "end":
        for k, v in XSH.completers.items():
            new[k] = v
        new[name] = func
    else:
        direction, rel = loc[0], loc[1:]
        found = False
        for k, v in XSH.completers.items():
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
    o = "Registered Completer Functions: (NX = Non Exclusive)\n\n"
    non_exclusive = " [NX]"
    _comp = XSH.completers
    ml = max((len(i) for i in _comp), default=0)
    exclusive_len = ml + len(non_exclusive) + 1
    _strs = []
    for c in _comp:
        if _comp[c].__doc__ is None:
            doc = "No description provided"
        else:
            doc = " ".join(_comp[c].__doc__.split())
        doc = justify(doc, 80, exclusive_len + 3)
        if is_exclusive_completer(_comp[c]):
            _strs.append("{: <{}} : {}".format(c, exclusive_len, doc))
        else:
            _strs.append("{: <{}} {} : {}".format(c, ml, non_exclusive, doc))
    return o + "\n".join(_strs) + "\n"


def complete_completer_names(xsh, **_):
    """Complete all loaded completer names"""
    for name, comp in xsh.completers.items():
        doc = NumpyDoc(comp)
        yield RichCompletion(name, description=doc.description)


def remove_completer(
    name: Annotated[str, Arg(completer=complete_completer_names)],
):
    """Removes a completer from xonsh

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
