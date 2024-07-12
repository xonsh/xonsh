import xonsh.cli_utils as xcli
from xonsh.built_ins import XSH
from xonsh.completers.completer import (
    add_one_completer,
    list_completers,
    remove_completer,
)
from xonsh.completers.tools import contextual_command_completer
from xonsh.parsers.completion_context import CommandContext

# for backward compatibility
_add_one_completer = add_one_completer


def _remove_completer(args):
    """for backward compatibility"""
    return remove_completer(args[0])


def complete_func_name_choices(xsh, **_):
    """Return all callable names in the current context"""
    for i, j in xsh.ctx.items():
        if callable(j):
            yield i


def complete_completer_pos_choices(xsh, **_):
    """Compute possible positions for the new completer"""
    yield from {"start", "end"}
    for k in xsh.completers.keys():
        yield ">" + k
        yield "<" + k


def _register_completer(
    name: str,
    func: xcli.Annotated[str, xcli.Arg(completer=complete_func_name_choices)],
    pos: xcli.Annotated[
        str, xcli.Arg(completer=complete_completer_pos_choices, nargs="?")
    ] = "start",
    _stack=None,
):
    """Add a new completer to xonsh

    Parameters
    ----------
    name
        unique name to use in the listing (run "completer list" to see the
        current completers in order)

    func
        the name of a completer function to use.  This should be a function
         that takes a Completion Context object and marked with the
         ``xonsh.completers.tools.contextual_completer`` decorator.
         It should return a set of valid completions
         for the given prefix.  If this completer should not be used in a given
         context, it should return an empty set or None.

         For more information see https://xon.sh/tutorial_completers.html#writing-a-new-completer.

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
                err = f"No such function: {func_name}"
    if err is None:
        _add_one_completer(name, func, pos)
    else:
        return None, err + "\n", 1


class CompleterAlias(xcli.ArgParserAlias):
    """CLI to add/remove/list xonsh auto-complete functions"""

    def complete(
        self,
        line: str,
    ):
        """Output the completions to stdout

        Parameters
        ----------
        line
            pass the CLI arguments as if they were typed
        prefix : -p, --prefix
            word at cursor

        Examples
        --------
        To get completions such as ``pip install``

            $ completer complete 'pip in'

        To get ``pip`` sub-commands, pass the command with a space at the end

            $ completer complete 'pip '
        """
        from xonsh.completer import Completer

        completer = Completer()
        completions, prefix_length = completer.complete_line(line)

        self.out(f"Prefix Length: {prefix_length}")
        for comp in completions:
            self.out(repr(comp))

    def build(self):
        parser = self.create_parser(prog="completer")
        parser.add_command(_register_completer, prog="add")
        parser.add_command(remove_completer, prog="remove", aliases=["rm"])
        parser.add_command(list_completers, prog="list", aliases=["ls"])
        parser.add_command(self.complete)
        return parser


completer_alias = CompleterAlias()


@contextual_command_completer
def complete_aliases(command: CommandContext):
    """Complete any alias that has ``xonsh_complete`` attribute.

    The said attribute should be a function. The current command context is passed to it.
    """

    if not command.args:
        return
    cmd = command.args[0].value

    if cmd not in XSH.aliases:
        # only complete aliases
        return
    alias = XSH.aliases.get(cmd)[0]  # type: ignore

    completer = getattr(alias, "xonsh_complete", None)
    if not completer:
        return

    if command.suffix:
        # completing in a middle of a word
        # (e.g. "completer some<TAB>thing")
        return

    possible = completer(command=command, alias=alias)
    return possible, False
