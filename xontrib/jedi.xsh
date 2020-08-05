"""Use Jedi as xonsh's python completer."""
import itertools

import xonsh
from xonsh.lazyasd import lazyobject, lazybool
from xonsh.completers.tools import (
    get_filter_function,
    get_ptk_completer,
    RichCompletion,
)

__all__ = ()

# an error will be printed in xontribs
# if jedi isn't installed
import jedi


@lazyobject
def PTK_COMPLETER():
    return get_ptk_completer()


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


def complete_jedi(prefix, line, start, end, ctx):
    """Completes python code using Jedi and xonsh operators"""

    # if this is the first word and it's a known command, don't complete.
    # taken from xonsh/completers/python.py
    if line.lstrip() != "":
        first = line.split(maxsplit=1)[0]
        if prefix == first and first in __xonsh__.commands_cache and first not in ctx:
            return set()

    filter_func = get_filter_function()
    jedi.settings.case_insensitive_completion = not __xonsh__.env.get(
        "CASE_SENSITIVE_COMPLETIONS"
    )

    if PTK_COMPLETER:  # 'is not None' won't work with lazyobject
        document = PTK_COMPLETER.current_document
        source = document.text
        row = document.cursor_position_row + 1
        column = document.cursor_position_col
    else:
        source = line
        row = 1
        column = end

    extra_ctx = {"__xonsh__": __xonsh__}
    try:
        extra_ctx['_'] = _
    except NameError:
        pass

    if JEDI_NEW_API:
        script = jedi.Interpreter(source, [ctx, extra_ctx])
    else:
        script = jedi.Interpreter(source, [ctx, extra_ctx], line=row,
                                  column=column)

    script_comp = set()
    try:
        if JEDI_NEW_API:
            script_comp = script.complete(row, column)
        else:
            script_comp = script.completions()
    except Exception:
        pass

    # make sure _* names are completed only when
    # the user writes the first underscore
    complete_underscores = prefix.endswith("_")

    return set(
        itertools.chain(
            (
                create_completion(comp)
                for comp in script_comp
                if complete_underscores or
                   not comp.name.startswith('_') or
                   not comp.complete.startswith("_")
            ),
            (t for t in XONSH_SPECIAL_TOKENS if filter_func(t, prefix)),
        )
    )


def create_completion(comp):
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

    return RichCompletion(
        comp.complete, display=display, description=description, prefix_len=0
    )


# monkey-patch the original python completer in 'base'.
xonsh.completers.base.complete_python = complete_jedi

# Jedi ignores leading '@(' and friends
completer remove python_mode

completer add jedi_python complete_jedi '<python'
completer remove python
