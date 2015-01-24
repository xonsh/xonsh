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
            msg += ['', '- ' + repr(a), '+ ' + repr(b)]
        msg = '\n'.join(msg)
        raise AssertionError(msg)

def check_token(input, exp):
    l = Lexer()
    l.build()
    l.input(input)
    obs = list(l)
    if len(obs) != 1:
        msg = 'The observed sequence does not have length-1: {0!r} != 1\n'
        msg += '# obs\n{1}'
        raise AssertionError(msg.format(len(obs), pformat(obs)))
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

def test_internal_whitespace():
    input = '42  +\t65'
    exp = [('INT_LITERAL', '42', 1, 0), 
           ('PLUS', '+', 1, 4),
           ('INT_LITERAL', '65', 1, 6),]
    yield check_tokens, input, exp

def test_indent_internal_whitespace():
    input = ' 42  +\t65'
    exp = [('INDENT', ' ', 1, 0),
           ('INT_LITERAL', '42', 1, 1), 
           ('PLUS', '+', 1, 5),
           ('INT_LITERAL', '65', 1, 7),]
    yield check_tokens, input, exp

def test_indent_internal_whitespace():
    input = ' 42  +\t65'
    exp = [('INDENT', ' ', 1, 0),
           ('INT_LITERAL', '42', 1, 1), 
           ('PLUS', '+', 1, 5),
           ('INT_LITERAL', '65', 1, 7),]
    yield check_tokens, input, exp

def test_assignment():
    input = 'x = 42'
    exp = [('ID', 'x', 1, 0),
           ('EQUALS', '=', 1, 2),
           ('INT_LITERAL', '42', 1, 4),] 
    yield check_tokens, input, exp

def test_multiline():
    input = 'x\ny'
    exp = [('ID', 'x', 1, 0),
           ('ID', 'y', 2, 2),]
    yield check_tokens, input, exp

def test_and():
    yield check_token, 'and', ['AND', 'and', 1, 0]

def test_single_quote_literal():
    yield check_token, "'yo'", ['STRING_LITERAL', "'yo'", 1, 0]

def test_double_quote_literal():
    yield check_token, '"yo"', ['STRING_LITERAL', '"yo"', 1, 0]

def test_triple_single_quote_literal():
    yield check_token, "'''yo'''", ['STRING_LITERAL', "'''yo'''", 1, 0]

def test_triple_double_quote_literal():
    yield check_token, '"""yo"""', ['STRING_LITERAL', '"""yo"""', 1, 0]

def test_single_raw_string_literal():
    yield check_token, "r'yo'", ['RAW_STRING_LITERAL', "r'yo'", 1, 0]

def test_double_raw_string_literal():
    yield check_token, 'r"yo"', ['RAW_STRING_LITERAL', 'r"yo"', 1, 0]

def test_single_unicode_literal():
    yield check_token, "u'yo'", ['UNICODE_LITERAL', "u'yo'", 1, 0]

def test_double_unicode_literal():
    yield check_token, 'u"yo"', ['UNICODE_LITERAL', 'u"yo"', 1, 0]

def test_single_bytes_literal():
    yield check_token, "b'yo'", ['BYTES_LITERAL', "b'yo'", 1, 0]

def test_double_bytes_literal():
    yield check_token, 'b"yo"', ['BYTES_LITERAL', 'b"yo"', 1, 0]



if __name__ == '__main__':
    nose.runmodule()