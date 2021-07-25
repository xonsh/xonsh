import collections
from xonsh.parsers.completion_context import CommandContext

from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    justify,
    is_exclusive_completer,
    complete_argparser,
    contextual_command_completer,
    get_filter_function,
)
from xonsh.cli_utils import Arg, Annotated, ArgCompleter


@contextual_command_completer
def complete_argparser_aliases(command: CommandContext):
    """Completer for any alias command that has ``argparser`` in ``parser`` attribute"""

    if not command.args:
        return
    cmd = command.args[0].value

    alias = XSH.aliases.get(cmd)  # type: ignore
    if not hasattr(alias, "parser"):
        return

    if command.suffix:
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return

    possible = complete_argparser(alias.parser, command=command, alias=alias)
    fltr = get_filter_function()
    for comp in possible:
        if fltr(comp, command.prefix):
            yield comp


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


class CompletersChoices(ArgCompleter):
    def __call__(self, xsh, **_):
        yield from xsh.completers.keys()


def remove_completer(
    name: Annotated[str, Arg(completer=CompletersChoices())],
):
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
