"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import Sequence
from pprint import pprint, pformat
sys.path.insert(0, os.path.abspath('..'))  # FIXME

import nose
from nose.tools import assert_equal

from ply.lex import LexToken

from xonsh.lexer import Lexer

LEXER_ARGS = {'lextab': 'lexer_test_table', 'debug': 0}

def ensure_tuple(x):
    if isinstance(x, LexToken):
        # line numbers can no longer be solely determined from the lexer
        #x = (x.type, x.value, x.lineno, x.lexpos)
        x = (x.type, x.value, x.lexpos)
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
    l.build(**LEXER_ARGS)
    l.input(input)
    obs = list(l)
    if len(obs) != 1:
        msg = 'The observed sequence does not have length-1: {0!r} != 1\n'
        msg += '# obs\n{1}'
        raise AssertionError(msg.format(len(obs), pformat(obs)))
    assert_token_equal(exp, obs[0])

def check_tokens(input, exp):
    l = Lexer()
    l.build(**LEXER_ARGS)
    l.input(input)
    obs = list(l)
    assert_tokens_equal(exp, obs)


def test_int_literal():
    yield check_token, '42', ['INT_LITERAL', 42, 0]

def test_hex_literal():
    yield check_token, '0x42', ['HEX_LITERAL', int('0x42', 16), 0]

def test_oct_o_literal():
    yield check_token, '0o42', ['OCT_LITERAL', int('0o42', 8), 0]

def test_oct_no_o_literal():
    yield check_token, '042', ['OCT_LITERAL', int('042', 8), 0]

def test_bin_literal():
    yield check_token, '0b101010', ['BIN_LITERAL', int('0b101010', 2), 0]

def test_indent():
    exp = [('INDENT', '  \t  ', 0), 
           ('INT_LITERAL', 42, 5)]
    yield check_tokens, '  \t  42', exp

def test_post_whitespace():
    input = '42  \t  '
    exp = [('INT_LITERAL', 42, 0)]
    yield check_tokens, input, exp

def test_internal_whitespace():
    input = '42  +\t65'
    exp = [('INT_LITERAL', 42, 0), 
           ('PLUS', '+', 4),
           ('INT_LITERAL', 65, 6),]
    yield check_tokens, input, exp

def test_indent_internal_whitespace():
    input = ' 42  +\t65'
    exp = [('INDENT', ' ', 0),
           ('INT_LITERAL', 42, 1), 
           ('PLUS', '+', 5),
           ('INT_LITERAL', 65, 7),]
    yield check_tokens, input, exp

def test_assignment():
    input = 'x = 42'
    exp = [('NAME', 'x', 0),
           ('EQUALS', '=', 2),
           ('INT_LITERAL', 42, 4),] 
    yield check_tokens, input, exp

def test_multiline():
    input = 'x\ny'
    exp = [('NAME', 'x', 0),
           ('NEWLINE', '\n', 1),
           ('NAME', 'y', 2),]
    yield check_tokens, input, exp

def test_and():
    yield check_token, 'and', ['AND', 'and', 0]

def test_single_quote_literal():
    yield check_token, "'yo'", ['STRING_LITERAL', "'yo'", 0]

def test_double_quote_literal():
    yield check_token, '"yo"', ['STRING_LITERAL', '"yo"', 0]

def test_triple_single_quote_literal():
    yield check_token, "'''yo'''", ['STRING_LITERAL', "'''yo'''", 0]

def test_triple_double_quote_literal():
    yield check_token, '"""yo"""', ['STRING_LITERAL', '"""yo"""', 0]

def test_single_raw_string_literal():
    yield check_token, "r'yo'", ['RAW_STRING_LITERAL', "r'yo'", 0]

def test_double_raw_string_literal():
    yield check_token, 'r"yo"', ['RAW_STRING_LITERAL', 'r"yo"', 0]

def test_single_unicode_literal():
    yield check_token, "u'yo'", ['UNICODE_LITERAL', "u'yo'", 0]

def test_double_unicode_literal():
    yield check_token, 'u"yo"', ['UNICODE_LITERAL', 'u"yo"', 0]

def test_single_bytes_literal():
    yield check_token, "b'yo'", ['BYTES_LITERAL', "b'yo'", 0]

def test_float_literals():
    cases = ['0.0', '.0', '0.', '1e10', '1.e42', '0.1e42', '0.5e-42', 
             '5E10', '5e+42']
    for s in cases:
        yield check_token, s, ['FLOAT_LITERAL', float(s), 0]


if __name__ == '__main__':
    nose.runmodule()