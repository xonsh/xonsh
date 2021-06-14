import collections

from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    justify,
    is_exclusive_completer,
    complete_argparser,
    contextual_command_completer,
)
from xonsh.cli_utils import Arg, ArgParserAlias, Annotated, ArgCompleter
from xonsh.parsers.completion_context import CommandContext


def _remove_completer(args):
    """for backward compatibility"""
    return remove_completer(args[0])


class FuncNameChoices(ArgCompleter):
    def __call__(self, xsh, **_):
        for i, j in xsh.ctx.items():
            if callable(j):
                yield i


class PosCompleter(ArgCompleter):
    def __call__(self, xsh, **_):
        yield from {"start", "end"}
        for k in xsh.completers.keys():
            yield ">" + k
            yield "<" + k


class CompletersChoices(ArgCompleter):
    def __call__(self, xsh, **_):
        yield from xsh.completers.keys()


def _register_completer(
    name: str,
    func: Annotated[str, Arg(completer=FuncNameChoices())],
    pos: Annotated[str, Arg(completer=PosCompleter(), nargs="?")] = "start",
    _stack=None,
):
    """adds a new completer to xonsh

    Parameters
    ----------
    name
        unique name to use in the listing (run "completer list" to see the
        current completers in order)

    func
        the name of a completer function to use.  This should be a function
         of the following arguments, and should return a set of valid completions
         for the given prefix.  If this completer should not be used in a given
         context, it should return an empty set or None.

         Arguments to FUNC:
           * prefix: the string to be matched
           * line: a string representing the whole current line, for context
           * begidx: the index at which prefix starts in line
           * endidx: the index at which prefix ends in line
           * ctx: the current Python environment

         If the completer expands the prefix in any way, it should return a tuple
         of two elements: the first should be the set of completions, and the
         second should be the length of the modified prefix (for an example, see
         xonsh.completers.path.complete_path).

    pos
        position into the list of completers at which the new
        completer should be added.  It can be one of the following values:
        * "start" indicates that the completer should be added to the start of
                 the list of completers (it should be run before all other exclusive completers)
        * "end" indicates that the completer should be added to the end of the
               list of completers (it should be run after all others)
        * ">KEY", where KEY is a pre-existing name, indicates that this should
                 be added after the completer named KEY
        * "<KEY", where KEY is a pre-existing name, indicates that this should
                 be added before the completer named KEY
    """
    err = None
    func_name = func
    xsh = XSH
    if name in xsh.completers:
        err = f"The name {name} is already a registered completer function."
    else:
        if func_name in xsh.ctx:
            func = xsh.ctx[func_name]
            if not callable(func):
                err = f"{func_name} is not callable"
        else:
            for frame_info in _stack:
                frame = frame_info[0]
                if func_name in frame.f_locals:
                    func = frame.f_locals[func_name]
                    break
                elif func_name in frame.f_globals:
                    func = frame.f_globals[func_name]
                    break
            else:
                err = "No such function: %s" % func_name
    if err is None:
        _add_one_completer(name, func, pos)
    else:
        return None, err + "\n", 1


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


# for backward compatibility
_add_one_completer = add_one_completer


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


class CompleterAlias(ArgParserAlias):
    """CLI to add/remove/list xonsh auto-complete functions"""

    def build(self):
        parser = self.create_parser(prog="completer")
        parser.add_command(_register_completer, prog="add")
        parser.add_command(remove_completer, prog="remove", aliases=["rm"])
        parser.add_command(list_completers, prog="list", aliases=["ls"])
        return parser


completer_alias = CompleterAlias()


@contextual_command_completer
def complete_argparser_aliases(command: CommandContext):
    """
    Completion for "completer"
    """
    if not command.args:
        return
    cmd = command.args[0].value

    alias = XSH.aliases.get(cmd)  # type: ignore
    if not hasattr(alias, "parser"):
        return

    if command.suffix:
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return None

    possible = complete_argparser(alias.parser, command=command, alias=alias)
    return {i for i in possible if i.startswith(command.prefix)}
