"""Bash-style brace expansion"""
# Copied verbatim from https://github.com/trendels/braceexpand
# braceexpand is Copyright (c) 2015 Stanis Trendelenburg
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import re
import string
import sys
from itertools import chain, product

__version__ = '0.1.2'

__all__ = ['braceexpand', 'alphabet', 'UnbalancedBracesError']

class UnbalancedBracesError(ValueError): pass

PY3 = sys.version_info[0] >= 3

if PY3:
    xrange = range

alphabet = string.ascii_uppercase + string.ascii_lowercase

int_range_re = re.compile(r'^(\d+)\.\.(\d+)(?:\.\.-?(\d+))?$')
char_range_re = re.compile(r'^([A-Za-z])\.\.([A-Za-z])(?:\.\.-?(\d+))?$')

def braceexpand(pattern, escape=True):
    """braceexpand(pattern) -> iterator over generated strings

    Returns an iterator over the strings resulting from brace expansion
    of pattern. This function implements Brace Expansion as described in
    bash(1), with the following limitations:

    * A pattern containing unbalanced braces will raise an
      UnbalancedBracesError exception. In bash, unbalanced braces will either
      be partly expanded or ignored.

    * A mixed-case character range like '{Z..a}' or '{a..Z}' will not
      include the characters '[]^_`' between 'Z' and 'a'.

    When escape is True (the default), characters in pattern can be
    prefixed with a backslash to cause them not to be interpreted as
    special characters for brace expansion (such as '{', '}', ',').
    To pass through a a literal backslash, double it ('\\\\').

    When escape is False, backslashes in pattern have no special
    meaning and will be preserved in the output.

    Examples:

    >>> from braceexpand import braceexpand

    # Integer range
    >>> list(braceexpand('item{1..3}'))
    ['item1', 'item2', 'item3']

    # Character range
    >>> list(braceexpand('{a..c}'))
    ['a', 'b', 'c']

    # Sequence
    >>> list(braceexpand('index.html{,.backup}'))
    ['index.html', 'index.html.backup']

    # Nested patterns
    >>> list(braceexpand('python{2.{5..7},3.{2,3}}'))
    ['python2.5', 'python2.6', 'python2.7', 'python3.2', 'python3.3']

    # Prefixing an integer with zero causes all numbers to be padded to
    # the same width.
    >>> list(braceexpand('{07..10}'))
    ['07', '08', '09', '10']

    # An optional increment can be specified for ranges.
    >>> list(braceexpand('{a..g..2}'))
    ['a', 'c', 'e', 'g']

    # Ranges can go in both directions.
    >>> list(braceexpand('{4..1}'))
    ['4', '3', '2', '1']

    # Unbalanced braces raise an exception.
    >>> list(braceexpand('{1{2,3}'))
    Traceback (most recent call last):
        ...
    UnbalancedBracesError: Unbalanced braces: '{1{2,3}'

    # By default, the backslash is the escape character.
    >>> list(braceexpand(r'{1\{2,3}'))
    ['1{2', '3']

    # Setting 'escape' to False disables backslash escaping.
    >>> list(braceexpand(r'\{1,2}', escape=False))
    ['\\\\1', '\\\\2']

    """
    return (_flatten(t, escape) for t in parse_pattern(pattern, escape))


def parse_pattern(pattern, escape):
    # pattern -> product(*parts)
    start = 0
    pos = 0
    bracketdepth = 0
    items = []

    #print 'pattern:', pattern
    while pos < len(pattern):
        if escape and pattern[pos] == '\\':
            pos += 2
            continue
        elif pattern[pos] == '{':
            if bracketdepth == 0 and pos > start:
                #print 'literal:', pattern[start:pos]
                items.append([pattern[start:pos]])
                start = pos
            bracketdepth += 1
        elif pattern[pos] == '}':
            bracketdepth -= 1
            if bracketdepth == 0:
                #print 'expression:', pattern[start+1:pos]
                items.append(parse_expression(pattern[start+1:pos], escape))
                start = pos + 1 # skip the closing brace
        pos += 1

    if bracketdepth != 0: # unbalanced braces
        raise UnbalancedBracesError("Unbalanced braces: '%s'" % pattern)

    if start < pos:
        #print 'literal:', pattern[start:]
        items.append([pattern[start:]])

    return product(*items)


def parse_expression(expr, escape):
    int_range_match = int_range_re.match(expr)
    if int_range_match:
        return make_int_range(*int_range_match.groups())

    char_range_match = char_range_re.match(expr)
    if char_range_match:
        return make_char_range(*char_range_match.groups())

    return parse_sequence(expr, escape)


def parse_sequence(seq, escape):
    # sequence -> chain(*sequence_items)
    start = 0
    pos = 0
    bracketdepth = 0
    items = []

    #print 'sequence:', seq
    while pos < len(seq):
        if escape and seq[pos] == '\\':
            pos += 2
            continue
        elif seq[pos] == '{':
            bracketdepth += 1
        elif seq[pos] == '}':
            bracketdepth -= 1
        elif seq[pos] == ',' and bracketdepth == 0:
            items.append(parse_pattern(seq[start:pos], escape))
            start = pos + 1 # skip the comma
        pos += 1

    if bracketdepth != 0 or not items: # unbalanced braces or not a sequence
        return iter(['{' + seq + '}'])

    # part after the last comma (may be the empty string)
    items.append(parse_pattern(seq[start:], escape))
    return chain(*items)


def make_int_range(start, end, step=None):
    if any([s[0] == '0' for s in (start, end) if s != '0']):
        padding = max(len(start), len(end))
    else:
        padding = 0
    step = int(step) if step else 1
    start = int(start)
    end = int(end)
    r = xrange(start, end+1, step) if start < end else \
        xrange(start, end-1, -step)
    return (str(i).rjust(padding, '0') for i in r)


def make_char_range(start, end, step=None):
    step = int(step) if step else 1
    start = alphabet.index(start)
    end = alphabet.index(end)
    return alphabet[start:end+1:step] if start < end else \
           alphabet[start:end-1:-step]


escape_re = re.compile(r'\\(.)')

def _flatten(t, escape):
    l = []
    for item in t:
        if isinstance(item, tuple): l.extend(_flatten(item, escape))
        else: l.append(item)
    s = ''.join(l)
    # Strip escape characters from generated strings after expansion.
    return escape_re.sub(r'\1', s) if escape else s


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.IGNORE_EXCEPTION_DETAIL)

