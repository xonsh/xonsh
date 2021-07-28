"""Use Jedi as xonsh's python completer."""
import os

import xonsh
from xonsh.lazyasd import lazyobject, lazybool
from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    get_filter_function,
    RichCompletion,
    contextual_completer,
)
from xonsh.completers import _aliases
from xonsh.parsers.completion_context import CompletionContext

__all__ = ()

# an error will be printed in xontribs
# if jedi isn't installed
import jedi


@lazybool
def JEDI_NEW_API():
    if hasattr(jedi, "__version__"):
        return tuple(map(int, jedi.__version__.split("."))) >= (0, 16, 0)
    else:
        return False


@lazyobject
def XONSH_SPECIAL_TOKENS():
    return {
        "?",
        "??",
        "$(",
        "${",
        "$[",
        "![",
        "!(",
        "@(",
        "@$(",
        "@",
    }


@lazyobject
def XONSH_SPECIAL_TOKENS_FIRST():
    return {tok[0] for tok in XONSH_SPECIAL_TOKENS}


@contextual_completer
def complete_jedi(context: CompletionContext):
    """Completes python code using Jedi and xonsh operators"""
    if context.python is None:
        return None

    ctx = context.python.ctx or {}

    # if the first word is a known command (and we're not completing it), don't complete.
    # taken from xonsh/completers/python.py
    if context.command and context.command.arg_index != 0:
        first = context.command.args[0].value
        if first in XSH.commands_cache and first not in ctx:  # type: ignore
            return None

    # if we're completing a possible command and the prefix contains a valid path, don't complete.
    if context.command:
        path_dir = os.path.dirname(context.command.prefix)
        if path_dir and os.path.isdir(os.path.expanduser(path_dir)):
            return None

    filter_func = get_filter_function()
    jedi.settings.case_insensitive_completion = not XSH.env.get(
        "CASE_SENSITIVE_COMPLETIONS"
    )

    source = context.python.multiline_code
    index = context.python.cursor_index
    row = source.count("\n", 0, index) + 1
    column = (
        index - source.rfind("\n", 0, index) - 1
    )  # will be `index - (-1) - 1` if there's no newline

    extra_ctx = {"__xonsh__": XSH}
    try:
        extra_ctx["_"] = _
    except NameError:
        pass

    if JEDI_NEW_API:
        script = jedi.Interpreter(source, [ctx, extra_ctx])
    else:
        script = jedi.Interpreter(source, [ctx, extra_ctx], line=row, column=column)

    script_comp = set()
    try:
        if JEDI_NEW_API:
            script_comp = script.complete(row, column)
        else:
            script_comp = script.completions()
    except Exception:
        pass

    res = set(create_completion(comp) for comp in script_comp if should_complete(comp))

    if index > 0:
        last_char = source[index - 1]
        res.update(
            RichCompletion(t, prefix_len=1)
            for t in XONSH_SPECIAL_TOKENS
            if filter_func(t, last_char)
        )
    else:
        res.update(RichCompletion(t, prefix_len=0) for t in XONSH_SPECIAL_TOKENS)

    return res


def should_complete(comp: jedi.api.classes.Completion):
    """
    make sure _* names are completed only when
    the user writes the first underscore
    """
    name = comp.name
    if not name.startswith("_"):
        return True
    completion = comp.complete
    # only if we're not completing the first underscore:
    return completion and len(completion) <= len(name) - 1


def create_completion(comp: jedi.api.classes.Completion):
    """Create a RichCompletion from a Jedi Completion object"""
    comp_type = None
    description = None

    if comp.type != "instance":
        sigs = comp.get_signatures()
        if sigs:
            comp_type = comp.type
            description = sigs[0].to_string()
    if comp_type is None:
        # jedi doesn't know exactly what this is
        inf = comp.infer()
        if inf:
            comp_type = inf[0].type
            description = inf[0].description

    display = comp.name + ("()" if comp_type == "function" else "")
    description = description or comp.type

    prefix_len = len(comp.name) - len(comp.complete)

    return RichCompletion(
        comp.name,
        display=display,
        description=description,
        prefix_len=prefix_len,
    )


# monkey-patch the original python completer in 'base'.
xonsh.completers.base.complete_python = complete_jedi

# Jedi ignores leading '@(' and friends
_aliases._add_one_completer("jedi_python", complete_jedi, "<python")
_aliases._remove_completer(["python"])
