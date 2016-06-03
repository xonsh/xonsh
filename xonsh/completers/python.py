import re
import sys
import inspect
import builtins
import importlib
from xonsh.tools import (subexpr_from_unbalanced, get_sep,
                         check_for_partial_string, RE_STRING_START)
from xonsh.completers.tools import get_filter_function, is_iterable

RE_ATTR = re.compile(r'([^\s\(\)]+(\.[^\s\(\)]+)*)\.(\w*)$')

XONSH_TOKENS = {
    'and ', 'as ', 'assert ', 'break', 'class ', 'continue', 'def ', 'del ',
    'elif ', 'else', 'except ', 'finally:', 'for ', 'from ', 'global ',
    'import ', 'if ', 'in ', 'is ', 'lambda ', 'nonlocal ', 'not ', 'or ',
    'pass', 'raise ', 'return ', 'try:', 'while ', 'with ', 'yield ', '+', '-',
    '/', '//', '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=', '>', '>=',
    '==', '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', '>>=', '<<=',
    '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', '${', '$[', '..',
    '...', '![', '!(',
}


def complete_python(prefix, line, start, end, ctx):
    """
    Completes based on the contents of the current Python environment,
    the Python built-ins, and xonsh operators.
    """
    first = line.split()[0]
    if first in builtins.__xonsh_commands_cache__ and first not in ctx:
        return None
    filt = get_filter_function()
    rtn = {s for s in XONSH_TOKENS if filt(s, prefix)}
    if ctx is not None:
        if '.' in prefix:
            rtn |= attr_complete(prefix, ctx, filt)
        rtn |= {s for s in ctx if filt(s, prefix)}
    rtn |= {s for s in dir(builtins) if filt(s, prefix)}
    return rtn


def complete_python_mode(prefix, line, start, end, ctx):
    """
    Python-mode completions for @( and ${
    """
    if not (prefix.startswith('@(') or prefix.startswith('${')):
        return set()
    prefix_start = prefix[:2]
    python_matches = complete_python(prefix[2:], line, start+2, end, ctx)
    return set(prefix_start + i for i in python_matches)


def attr_complete(prefix, ctx, filter_func):
    """Complete attributes of an object."""
    attrs = set()
    m = RE_ATTR.match(prefix)
    if m is None:
        return attrs
    expr, attr = m.group(1, 3)
    expr = subexpr_from_unbalanced(expr, '(', ')')
    expr = subexpr_from_unbalanced(expr, '[', ']')
    expr = subexpr_from_unbalanced(expr, '{', '}')
    _ctx = None
    xonsh_safe_eval = builtins.__xonsh_execer__.eval
    try:
        val = xonsh_safe_eval(expr, ctx, wrap_subprocs=False)
        _ctx = ctx
    except:  # pylint:disable=bare-except
        try:
            val = xonsh_safe_eval(expr, builtins.__dict__, wrap_subprocs=False)
            _ctx = builtins.__dict__
        except:  # pylint:disable=bare-except
            return attrs  # anything could have gone wrong!
    if len(attr) == 0:
        opts = [o for o in dir(val) if not o.startswith('_')]
    else:
        opts = [o for o in dir(val) if filter_func(o, attr)]
    prelen = len(prefix)
    for opt in opts:
        # check whether these options actually work (e.g., disallow 7.imag)
        try:
            _val = '{0}.{1}'.format(expr, opt)
            xonsh_safe_eval(_val, _ctx, wrap_subprocs=False)
        except:  # pylint:disable=bare-except
            continue
        a = getattr(val, opt)
        if callable(a):
            rpl = opt + '('
        elif is_iterable(a):
            rpl = opt + '['
        else:
            rpl = opt
        # note that prefix[:prelen-len(attr)] != prefix[:-len(attr)]
        # when len(attr) == 0.
        comp = prefix[:prelen - len(attr)] + rpl
        attrs.add(comp)
    return attrs


def complete_import(prefix, line, start, end, ctx):
    """
    Completes module names and contents for "import ..." and "from ... import
    ..."
    """
    ltoks = line.split()
    if len(ltoks) == 2 and ltoks[0] == 'from':
        # completing module to import
        return {'{} '.format(i) for i in complete_module(prefix)}
    if ltoks[0] == 'import' and start == len('import '):
        # completing module to import
        return complete_module(prefix)
    if len(ltoks) > 2 and ltoks[0] == 'from' and ltoks[2] == 'import':
        # complete thing inside a module
        try:
            mod = importlib.import_module(ltoks[1])
        except ImportError:
            return set()
        out = {i[0]
               for i in inspect.getmembers(mod)
               if i[0].startswith(prefix)}
        return out
    return set()


def complete_module(prefix):
    return {s for s in sys.modules if get_filter_function()(s, prefix)}
