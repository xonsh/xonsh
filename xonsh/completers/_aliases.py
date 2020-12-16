import argparse as ap
import builtins

import xonsh.cli_utils as xcli
import xonsh.lazyasd as xl
from xonsh.completers.completer import (
    list_completers,
    remove_completer,
    add_one_completer,
)

# for backward compatibility
_add_one_completer = add_one_completer


def _remove_completer(args):
    """for backward compatibility"""
    return remove_completer(args[0])


def _register_completer(name: str, func: str, pos="start", stack=None):
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
                 the list of completers (it should be run before all others)
        * "end" indicates that the completer should be added to the end of the
               list of completers (it should be run after all others)
        * ">KEY", where KEY is a pre-existing name, indicates that this should
                 be added after the completer named KEY
        * "<KEY", where KEY is a pre-existing name, indicates that this should
                 be added before the completer named KEY
        (Default value: "start")
    """
    err = None
    func_name = func
    xsh = builtins.__xonsh__  # type: ignore
    if name in xsh.completers:
        err = f"The name {name} is already a registered completer function."
    else:
        if func_name in xsh.ctx:
            func = xsh.ctx[func_name]
            if not callable(func):
                err = f"{func_name} is not callable"
        else:
            for frame_info in stack:
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


@xl.lazyobject
def _parser() -> ap.ArgumentParser:
    parser = xcli.make_parser(completer_alias)
    commands = parser.add_subparsers(title="commands")

    xcli.make_parser(
        _register_completer,
        commands,
        params={
            "name": {},
            "func": {},
            "pos": {"default": "start", "nargs": "?"},
        },
        prog="add",
    )

    xcli.make_parser(
        remove_completer,
        commands,
        params={"name": {}},
        prog="remove",
    )

    xcli.make_parser(list_completers, commands, prog="list")
    return parser


def completer_alias(args, stdin=None, stdout=None, stderr=None, spec=None, stack=None):
    """CLI to add/remove/list xonsh auto-complete functions"""
    ns = _parser.parse_args(args)
    kwargs = vars(ns)
    return xcli.dispatch(**kwargs, stdin=stdin, stdout=stdout, stack=stack)
