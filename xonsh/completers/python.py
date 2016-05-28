import re
import builtins
from xonsh.tools import (subexpr_from_unbalanced, get_sep,
                         check_for_partial_string, RE_STRING_START)


def is_iterable(x):
    try:
        _ = iter(x)
        return True
    except:
        return False

RE_ATTR = re.compile(r'([^\s\(\)]+(\.[^\s\(\)]+)*)\.(\w*)$')

XONSH_TOKENS = {
    'and ', 'as ', 'assert ', 'break', 'class ', 'continue', 'def ', 'del ',
    'elif ', 'else', 'except ', 'finally:', 'for ', 'from ', 'global ',
    'import ', 'if ', 'in ', 'is ', 'lambda ', 'nonlocal ', 'not ', 'or ',
    'pass', 'raise ', 'return ', 'try:', 'while ', 'with ', 'yield ', '+', '-',
    '/', '//', '%', '**', '|', '&', '~', '^', '>>', '<<', '<', '<=', '>', '>=',
    '==', '!=', '->', '=', '+=', '-=', '*=', '/=', '%=', '**=', '>>=', '<<=',
    '&=', '^=', '|=', '//=', ',', ';', ':', '?', '??', '$(', '${', '$[', '..',
    '...'
}


def complete_python(prefix, line, start, end, ctx):
    csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
    if csc:
        def filt(s, x): return s.startswith(x)
    else:
        def filt(s, x): return s.lower().startswith(x.lower())
    rtn = {s for s in XONSH_TOKENS if filt(s, prefix)}
    if ctx is not None:
        if '.' in prefix:
            rtn |= attr_complete(prefix, ctx, filt)
        rtn |= {s for s in ctx if filt(s, prefix)}
    rtn |= {s for s in dir(builtins) if filt(s, prefix)}
    return rtn


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
    try:
        val = eval(expr, ctx)
        _ctx = ctx
    except:  # pylint:disable=bare-except
        try:
            val = eval(expr, builtins.__dict__)
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
            eval('{0}.{1}'.format(expr, opt), _ctx)
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
