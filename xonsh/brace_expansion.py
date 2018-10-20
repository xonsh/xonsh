import itertools
import re

from xonsh.lazyasd import LazyObject

# regex to be used for splitting on braced regions
BRACED = LazyObject(lambda: re.compile(r"(?<!\\)(\{.*?(?<!\\)\})"), globals(), "BRACED")


def split(string, splitter):
    """string-splitting function that ignores the first and last
    characters of the string.
    """
    if len(string) <= 1:
        return [string]
    new = string[1:-1].split(splitter)
    if len(new) == 1:
        return [string]
    new[0] = string[0] + new[0]
    new[-1] += string[-1]
    return new


def int_range(p1, p2):
    """expand a range of integers into integer-strings with the desired
    padding. i.e. 08..10 becomes 08 09 10 whereas 8..10 becomse 8 9 10.
    """
    n1, n2 = int(p1), int(p2)
    pad = len(p1)
    return ("{:0{}d}".format(n, pad) for n in range(n1, n2 + 1))


def range_expand(string):
    """for one comma-separated item from a brace expansion, determine
    whether or not it is a range and expand accordingly.
    """
    parts = split(string, "..")
    # no range. return a list containing the original string.
    if len(parts) == 1:
        return parts
    # ensure range has only two parts.
    assert len(parts) == 2, "range %s has too many parts" % string

    # attempt to parse as a range of integers
    try:
        return int_range(*parts)
    except ValueError:
        pass

    # attempt to parse as a range of characters
    p1, p2 = parts
    return map(chr, range(ord(p1), ord(p2) + 1))


def inner_brace_expand(string):
    """parse a brace expansion in a way similar to Bash. Input string
    should not include braces.
    """
    # split on commas.
    return itertools.chain(*map(range_expand, split(string, ",")))


def brace_expand(string):
    """takes a string as input and interprets in a way similar to Bash
    arguments with brace expansion and globbing. returns an iterator.

    >>> list(brace_expand('{a,b}{c..e}{09..10}'))
    ['ac09', 'ac10', 'ad09', 'ad10', 'ae09', 'ae10', 'bc09', 'bc10', 'bd09', 'bd10', 'be09', 'be10']
    """
    parts = BRACED.split(string)
    newparts = []

    for part in parts:
        if not part:
            continue

        # remove backslashes from escaped braces
        unescaped = part.replace(r"\{", "{").replace(r"\}", "}")
        # part requires brace expansion.
        if part[0] == "{":
            newparts.append(inner_brace_expand(unescaped[1:-1]))
        else:
            newparts.append([unescaped])
    # generate and join the cartesian product of all expansions
    product = itertools.product(*(p for p in newparts if p))
    strings = ("".join(i) for i in product)
    return strings
