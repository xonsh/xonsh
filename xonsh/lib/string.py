from collections.abc import Iterable


def commonprefix(m: Iterable[str]) -> str:
    """Given an iterable of strings, returns the longest common leading substring"""
    m = list(m)
    if not m:
        return ""
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1


def unquote(s: str, chars: str = "'\"") -> str:
    """Strip one pair of matching quote characters from a string."""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in chars:
        return s[1:-1]
    return s


def endswith_newline(s: str) -> str:
    """Return a string ending with exactly one newline character."""
    return s.rstrip("\n") + "\n"


def is_balanced(expr: str, ltok: str, rtok: str) -> bool:
    """Determines whether an expression has unbalanced opening and closing tokens."""
    lcnt = expr.count(ltok)
    if lcnt == 0:
        return True
    rcnt = expr.count(rtok)
    if lcnt == rcnt:
        return True
    else:
        return False


def subexpr_from_unbalanced(expr: str, ltok: str, rtok: str) -> str:
    """Attempts to pull out a valid subexpression for unbalanced grouping,
    based on opening tokens, eg. '(', and closing tokens, eg. ')'.  This
    does not do full tokenization, but should be good enough for tab
    completion.
    """
    if is_balanced(expr, ltok, rtok):
        return expr
    subexpr = expr.rsplit(ltok, 1)[-1]
    subexpr = subexpr.rsplit(",", 1)[-1]
    subexpr = subexpr.rsplit(":", 1)[-1]
    return subexpr


def subexpr_before_unbalanced(expr: str, ltok: str, rtok: str) -> str:
    """Obtains the expression prior to last unbalanced left token."""
    subexpr, _, post = expr.rpartition(ltok)
    nrtoks_in_post = post.count(rtok)
    while nrtoks_in_post != 0:
        for _ in range(nrtoks_in_post):
            subexpr, _, post = subexpr.rpartition(ltok)
        nrtoks_in_post = post.count(rtok)
    _, _, subexpr = subexpr.rpartition(rtok)
    _, _, subexpr = subexpr.rpartition(ltok)
    return subexpr
