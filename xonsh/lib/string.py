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
