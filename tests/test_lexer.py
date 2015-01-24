"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import Sequence
from pprint import pprint, pformat
sys.path.insert(0, os.path.abspath('..'))

import nose
from nose.tools import assert_equal

from ply.lex import LexToken

from xonsh.lexer import Lexer


def ensure_tuple(x):
    if isinstance(x, LexToken):
        x = (x.type, x.value, x.lineno, x.lexpos)
    elif isinstance(x, tuple):
        pass
    elif isinstance(x, Sequence):
        x = tuple(x)
    else:
        raise TypeError('{0} is not a sequence'.format(x))
    return x

def tokens_equal(x, y):
    """Tests whether two token are equal."""
    xtup = ensure_tuple(x)
    ytup = ensure_tuple(y)
    return xtup == ytup

def assert_token_equal(x, y):
    """Asserts that two tokens are equal."""
    if not tokens_equal(x, y):
        msg = 'The tokens differ: {0!r} != {1!r}'.format(x, y)
        raise AssertionError(msg)

def assert_tokens_equal(x, y):
    """Asserts that two token sequences are equal."""
    if len(x) != len(y):
        msg = 'The tokens sequences have different lengths: {0!r} != {1!r}\n'
        msg += '# x\n{2}\n\n# y\n{3}'
        raise AssertionError(msg.format(len(x), len(y), pformat(x), pformat(y)))
    diffs = []
    diffs = [(a, b) for a, b in zip(x, y) if not tokens_equal(a, b)]
    if len(diffs) > 0:
        msg = ['The token sequnces differ: ']
        for a, b in diffs:
            msg += ['', '- ' + repr(x), '+ ' + repr(y)]
        msg = '\n'.join(msg)
        raise AssertionError(msg)

def check_token(input, exp):
    l = Lexer()
    l.build()
    l.input(input)
    obs = list(l)
    assert_equal(1, len(obs))
    assert_token_equal(exp, obs[0])

def check_tokens(input, exp):
    l = Lexer()
    l.build()
    l.input(input)
    obs = list(l)
    assert_tokens_equal(exp, obs)


def test_int_literal():
    yield check_token, '42', ['INT_LITERAL', '42', 1, 0]

def test_indent():
    exp = [('INDENT', '  \t  ', 1, 0), ('INT_LITERAL', '42', 1, 5)]
    yield check_tokens, '  \t  42', exp

def test_post_whitespace():
    input = '42  \t  '
    exp = [('INT_LITERAL', '42', 1, 0)]
    yield check_tokens, input, exp



if __name__ == '__main__':
    nose.runmodule()