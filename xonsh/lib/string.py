from collections.abc import Iterable


def commonprefix(m: Iterable[str]) -> str:
    """Given an iterable of strings, returns the longest common leading substring"""
    if not m:
        return ""
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1
