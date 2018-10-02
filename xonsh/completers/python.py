"""Completers for Python code"""
import re
import sys
import inspect
import builtins
import importlib
import collections.abc as cabc

import xonsh.tools as xt
import xonsh.lazyasd as xl

from xonsh.completers.tools import get_filter_function


@xl.lazyobject
def RE_ATTR():
    return re.compile(r"([^\s\(\)]+(\.[^\s\(\)]+)*)\.(\w*)$")


@xl.lazyobject
def XONSH_EXPR_TOKENS():
    return {
        "and ",
        "else",
        "for ",
        "if ",
        "in ",
        "is ",
        "lambda ",
        "not ",
        "or ",
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
        ",",
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
        "as ",
        "assert ",
        "break",
        "class ",
        "continue",
        "def ",
        "del ",
        "elif ",
        "except ",
        "finally:",
        "from ",
        "global ",
        "import ",
        "nonlocal ",
        "pass",
        "raise ",
        "return ",
        "try:",
        "while ",
        "with ",
        "yield ",
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


def complete_python(prefix, line, start, end, ctx):
    """
    Completes based on the contents of the current Python environment,
    the Python built-ins, and xonsh operators.
    If there are no matches, split on common delimiters and try again.
    """
    rtn = _complete_python(prefix, line, start, end, ctx)
    if not rtn:
        prefix = (
            re.split(r"\(|=|{|\[|,", prefix)[-1]
            if not prefix.startswith(",")
            else prefix
        )
        start = line.find(prefix)
        rtn = _complete_python(prefix, line, start, end, ctx)
        return rtn, len(prefix)
    return rtn


def _complete_python(prefix, line, start, end, ctx):
    """
    Completes based on the contents of the current Python environment,
    the Python built-ins, and xonsh operators.
    """
    if line != "":
        first = line.split()[0]
        if first in builtins.__xonsh__.commands_cache and first not in ctx:
            return set()
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


def complete_python_mode(prefix, line, start, end, ctx):
    """
    Python-mode completions for @( and ${
    """
    if not (prefix.startswith("@(") or prefix.startswith("${")):
        return set()
    prefix_start = prefix[:2]
    python_matches = complete_python(prefix[2:], line, start - 2, end - 2, ctx)
    if isinstance(python_matches, cabc.Sequence):
        python_matches = python_matches[0]
    return set(prefix_start + i for i in python_matches)


def _safe_eval(expr, ctx):
    """Safely tries to evaluate an expression. If this fails, it will return
    a (None, None) tuple.
    """
    _ctx = None
    xonsh_safe_eval = builtins.__xonsh__.execer.eval
    try:
        val = xonsh_safe_eval(expr, ctx, ctx, transform=False)
        _ctx = ctx
    except:  # pylint:disable=bare-except
        try:
            val = xonsh_safe_eval(expr, builtins.__dict__, transform=False)
            _ctx = builtins.__dict__
        except:  # pylint:disable=bare-except
            val = _ctx = None
    return val, _ctx


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
        _expr = "{0}.{1}".format(expr, opt)
        _val_, _ctx_ = _safe_eval(_expr, _ctx)
        if _val_ is None and _ctx_ is None:
            continue
        a = getattr(val, opt)
        if builtins.__xonsh__.env["COMPLETIONS_BRACKETS"]:
            if callable(a):
                rpl = opt + "("
            elif isinstance(a, (cabc.Sequence, cabc.Mapping)):
                rpl = opt + "["
            else:
                rpl = opt
        else:
            rpl = opt
        # note that prefix[:prelen-len(attr)] != prefix[:-len(attr)]
        # when len(attr) == 0.
        comp = prefix[: prelen - len(attr)] + rpl
        attrs.add(comp)
    return attrs


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
    except ValueError:
        return set()
    args = {p + "=" for p in sig.parameters if filter_func(p, prefix)}
    return args


def complete_import(prefix, line, start, end, ctx):
    """
    Completes module names and contents for "import ..." and "from ... import
    ..."
    """
    ltoks = line.split()
    ntoks = len(ltoks)
    if ntoks == 2 and ltoks[0] == "from":
        # completing module to import
        return {"{} ".format(i) for i in complete_module(prefix)}
    if ntoks > 1 and ltoks[0] == "import" and start == len("import "):
        # completing module to import
        return complete_module(prefix)
    if ntoks > 2 and ltoks[0] == "from" and ltoks[2] == "import":
        # complete thing inside a module
        try:
            mod = importlib.import_module(ltoks[1])
        except ImportError:
            return set()
        out = {i[0] for i in inspect.getmembers(mod) if i[0].startswith(prefix)}
        return out
    return set()


def complete_module(prefix):
    return {s for s in sys.modules if get_filter_function()(s, prefix)}
