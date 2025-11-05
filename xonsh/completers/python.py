"""Completers for Python code"""

import builtins
import collections.abc as cabc
import inspect
import re
import warnings

import xonsh.lib.lazyasd as xl
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    CompleterResult,
    RichCompletion,
    contextual_completer,
    get_filter_function,
)
from xonsh.parsers.completion_context import CompletionContext, PythonContext


@xl.lazyobject
def RE_ATTR():
    return re.compile(r"([^\s\(\)]+(\.[^\s\(\)]+)*)\.(\w*)$")


@xl.lazyobject
def XONSH_EXPR_TOKENS():
    return {
        RichCompletion("and", append_space=True),
        "else",
        RichCompletion("for", append_space=True),
        RichCompletion("if", append_space=True),
        RichCompletion("in", append_space=True),
        RichCompletion("is", append_space=True),
        RichCompletion("lambda", append_space=True),
        RichCompletion("not", append_space=True),
        RichCompletion("or", append_space=True),
        "+",
        "-",
        "/",
        "//",
        "%",
        "**",
        "|",
        "&",
        "~",
        "^",
        ">>",
        "<<",
        "<",
        "<=",
        ">",
        ">=",
        "==",
        "!=",
        RichCompletion(",", append_space=True),
        "?",
        "??",
        "$(",
        "${",
        "$[",
        "...",
        "![",
        "!(",
        "@(",
        "@$(",
        "@",
    }


@xl.lazyobject
def XONSH_STMT_TOKENS():
    return {
        RichCompletion("as", append_space=True),
        RichCompletion("assert", append_space=True),
        "break",
        RichCompletion("class", append_space=True),
        "continue",
        RichCompletion("def", append_space=True),
        RichCompletion("del", append_space=True),
        RichCompletion("elif", append_space=True),
        RichCompletion("except", append_space=True),
        "finally:",
        RichCompletion("from", append_space=True),
        RichCompletion("global", append_space=True),
        RichCompletion("import", append_space=True),
        RichCompletion("nonlocal", append_space=True),
        "pass",
        RichCompletion("raise", append_space=True),
        RichCompletion("return", append_space=True),
        "try:",
        RichCompletion("while", append_space=True),
        RichCompletion("with", append_space=True),
        RichCompletion("yield", append_space=True),
        "-",
        "/",
        "//",
        "%",
        "**",
        "|",
        "&",
        "~",
        "^",
        ">>",
        "<<",
        "<",
        "<=",
        "->",
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "**=",
        ">>=",
        "<<=",
        "&=",
        "^=",
        "|=",
        "//=",
        ";",
        ":",
        "..",
    }


@xl.lazyobject
def XONSH_TOKENS():
    return set(XONSH_EXPR_TOKENS) | set(XONSH_STMT_TOKENS)


@xl.lazyobject
def RE_XONSH_IMP():
    """Regex pattern to match __xonsh__.imp.<module> syntax."""
    return re.compile(r"__xonsh__\.imp\.([a-zA-Z_][\w\.]*)?$")


@contextual_completer
def complete_xonsh_imp(context: CompletionContext) -> CompleterResult:
    """
    Completes module names for the inline xonsh importer (__xonsh__.imp.<module>).
    """
    if context.python is None:
        return None

    line = context.python.multiline_code
    prefix = (line.rsplit(maxsplit=1) or [""])[-1]

    # Check if we're completing __xonsh__.imp.<module>
    m = RE_XONSH_IMP.search(prefix)
    if m is None:
        return None

    # Extract the module path after __xonsh__.imp.
    module_path = m.group(1) or ""

    # Import the necessary functions from the imports completer
    from xonsh.completers.imports import (
        filter_completions,
        get_root_modules,
        try_import,
    )

    # Handle nested module paths (e.g., os.path)
    if "." in module_path:
        # Split into base module and submodule path
        parts = module_path.split(".")
        base_module = ".".join(parts[:-1])
        prefix_part = parts[-1]

        # Try to get completions for the submodule
        try:
            submodule_completions = try_import(base_module, only_modules=True)
            full_prefix = f"__xonsh__.imp.{base_module}."
            completions = {
                full_prefix + comp
                for comp in filter_completions(prefix_part, submodule_completions)
            }
            return completions, len(prefix)
        except Exception:
            return None
    else:
        # Complete root-level module names
        modules = get_root_modules()
        full_prefix = "__xonsh__.imp."
        completions = {
            full_prefix + mod for mod in filter_completions(module_path, modules)
        }
        return completions, len(prefix)


@contextual_completer
def complete_python(context: CompletionContext) -> CompleterResult:
    """
    Completes based on the contents of the current Python environment,
    the Python built-ins, and xonsh operators.
    """
    # If there are no matches, split on common delimiters and try again.
    if context.python is None:
        return None

    if context.command and context.command.arg_index != 0:
        # this can be a command (i.e. not a subexpression)
        first = context.command.args[0].value
        ctx = context.python.ctx or {}
        if first in XSH.commands_cache and first not in ctx:  # type: ignore
            # this is a known command, so it won't be python code
            return None

    line = context.python.multiline_code
    prefix = (line.rsplit(maxsplit=1) or [""])[-1]
    rtn = _complete_python(prefix, context.python)
    if not rtn:
        prefix = (
            re.split(r"\(|=|{|\[|,", prefix)[-1]
            if not prefix.startswith(",")
            else prefix
        )
        rtn = _complete_python(prefix, context.python)
    return rtn, len(prefix)


def _complete_python(prefix, context: PythonContext):
    """
    Completes based on the contents of the current Python environment,
    the Python built-ins, and xonsh operators.
    """
    line = context.multiline_code
    end = context.cursor_index
    ctx = context.ctx
    filt = get_filter_function()
    rtn = set()
    if ctx is not None:
        if "." in prefix:
            rtn |= attr_complete(prefix, ctx, filt)
        args = python_signature_complete(prefix, line, end, ctx, filt)
        rtn |= args
        rtn |= {s for s in ctx if filt(s, prefix)}
    else:
        args = ()
    if len(args) == 0:
        # not in a function call, so we can add non-expression tokens
        rtn |= {s for s in XONSH_TOKENS if filt(s, prefix)}
    else:
        rtn |= {s for s in XONSH_EXPR_TOKENS if filt(s, prefix)}
    rtn |= {s for s in dir(builtins) if filt(s, prefix)}
    return rtn


def _turn_off_warning(func):
    """Decorator to turn off warning temporarily."""

    def wrapper(*args, **kwargs):
        warnings.filterwarnings("ignore")
        r = func(*args, **kwargs)
        warnings.filterwarnings("once", category=DeprecationWarning)
        return r

    return wrapper


def _safe_eval(expr, ctx):
    """Safely tries to evaluate an expression. If this fails, it will return
    a (None, None) tuple.
    """
    _ctx = None
    xonsh_safe_eval = XSH.execer.eval
    try:
        val = xonsh_safe_eval(expr, ctx, ctx, transform=False)
        _ctx = ctx
    except Exception:
        try:
            val = xonsh_safe_eval(expr, builtins.__dict__, transform=False)
            _ctx = builtins.__dict__
        except Exception:
            val = _ctx = None
    return val, _ctx


@_turn_off_warning
def attr_complete(prefix, ctx, filter_func):
    """Complete attributes of an object."""
    attrs = set()
    m = RE_ATTR.match(prefix)
    if m is None:
        return attrs
    expr, attr = m.group(1, 3)
    expr = xt.subexpr_from_unbalanced(expr, "(", ")")
    expr = xt.subexpr_from_unbalanced(expr, "[", "]")
    expr = xt.subexpr_from_unbalanced(expr, "{", "}")
    val, _ctx = _safe_eval(expr, ctx)
    if val is None and _ctx is None:
        return attrs
    if len(attr) == 0:
        opts = [o for o in dir(val) if not o.startswith("_")]
    else:
        opts = [o for o in dir(val) if filter_func(o, attr)]
    prelen = len(prefix)
    for opt in opts:
        # check whether these options actually work (e.g., disallow 7.imag)
        _expr = f"{expr}.{opt}"
        _val_, _ctx_ = _safe_eval(_expr, _ctx)
        if _val_ is None and _ctx_ is None:
            continue
        a = getattr(val, opt)
        if XSH.env["COMPLETIONS_BRACKETS"]:
            if callable(a):
                # Determine if this callable has useful attributes (class/module/namespace)
                has_useful_attrs = (
                    inspect.isclass(a)
                    or inspect.ismodule(a)
                    or any(not attr.startswith("_") for attr in dir(a))
                )

                base_comp = prefix[: prelen - len(attr)] + opt

                if has_useful_attrs:
                    # Show plain name for attribute access (e.g., classes, modules)
                    attrs.add(base_comp)
                else:
                    # Show with ( for calling (e.g., simple functions, methods)
                    attrs.add(base_comp + "(")
            elif isinstance(a, cabc.Sequence | cabc.Mapping):
                rpl = opt + "["
                comp = prefix[: prelen - len(attr)] + rpl
                attrs.add(comp)
            else:
                rpl = opt
                comp = prefix[: prelen - len(attr)] + rpl
                attrs.add(comp)
        else:
            rpl = opt
            comp = prefix[: prelen - len(attr)] + rpl
            attrs.add(comp)
    return attrs


@_turn_off_warning
def python_signature_complete(prefix, line, end, ctx, filter_func):
    """Completes a python function (or other callable) call by completing
    argument and keyword argument names.
    """
    front = line[:end]
    if xt.is_balanced(front, "(", ")"):
        return set()
    funcname = xt.subexpr_before_unbalanced(front, "(", ")")
    val, _ctx = _safe_eval(funcname, ctx)
    if val is None:
        return set()
    try:
        sig = inspect.signature(val)
    except (ValueError, TypeError):
        return set()
    args = {p + "=" for p in sig.parameters if filter_func(p, prefix)}
    return args
