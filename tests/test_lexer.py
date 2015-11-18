# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import Sequence
sys.path.insert(0, os.path.abspath('..'))  # FIXME
from pprint import pformat

import nose

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
        msg = ['The token sequences differ: ']
        for a, b in diffs:
            msg += ['', '- ' + repr(a), '+ ' + repr(b)]
        msg = '\n'.join(msg)
        raise AssertionError(msg)

def check_token(inp, exp):
    l = Lexer()
    l.input(inp)
    obs = list(l)
    if len(obs) != 1:
        msg = 'The observed sequence does not have length-1: {0!r} != 1\n'
        msg += '# obs\n{1}'
        raise AssertionError(msg.format(len(obs), pformat(obs)))
    assert_token_equal(exp, obs[0])

def check_tokens(inp, exp):
    l = Lexer()
    l.input(inp)
    obs = list(l)
    assert_tokens_equal(exp, obs)

def check_tokens_subproc(inp, exp):
    l = Lexer()
    l.input('$[{}]'.format(inp))
    obs = list(l)[1:-1]
    assert_tokens_equal(exp, obs)

def test_int_literal():
    yield check_token, '42', ['NUMBER', '42', 0]

def test_hex_literal():
    yield check_token, '0x42', ['NUMBER', '0x42', 0]

def test_oct_o_literal():
    yield check_token, '0o42', ['NUMBER', '0o42', 0]

def test_bin_literal():
    yield check_token, '0b101010', ['NUMBER', '0b101010', 0]

def test_indent():
    exp = [('INDENT', '  \t  ', 0),
           ('NUMBER', '42', 5),
           ('DEDENT', '', 0)]
    yield check_tokens, '  \t  42', exp

def test_post_whitespace():
    inp = '42  \t  '
    exp = [('NUMBER', '42', 0)]
    yield check_tokens, inp, exp

def test_internal_whitespace():
    inp = '42  +\t65'
    exp = [('NUMBER', '42', 0),
           ('PLUS', '+', 4),
           ('NUMBER', '65', 6),]
    yield check_tokens, inp, exp

def test_indent_internal_whitespace():
    inp = ' 42  +\t65'
    exp = [('INDENT', ' ', 0),
           ('NUMBER', '42', 1),
           ('PLUS', '+', 5),
           ('NUMBER', '65', 7),
           ('DEDENT', '', 0)]
    yield check_tokens, inp, exp

def test_assignment():
    inp = 'x = 42'
    exp = [('NAME', 'x', 0),
           ('EQUALS', '=', 2),
           ('NUMBER', '42', 4),]
    yield check_tokens, inp, exp

def test_multiline():
    inp = 'x\ny'
    exp = [('NAME', 'x', 0),
           ('NEWLINE', '\n', 1),
           ('NAME', 'y', 0),]
    yield check_tokens, inp, exp

def test_and():
    yield check_token, 'and', ['AND', 'and', 0]

def test_single_quote_literal():
    yield check_token, "'yo'", ['STRING', "'yo'", 0]

def test_double_quote_literal():
    yield check_token, '"yo"', ['STRING', '"yo"', 0]

def test_triple_single_quote_literal():
    yield check_token, "'''yo'''", ['STRING', "'''yo'''", 0]

def test_triple_double_quote_literal():
    yield check_token, '"""yo"""', ['STRING', '"""yo"""', 0]

def test_single_raw_string_literal():
    yield check_token, "r'yo'", ['STRING', "r'yo'", 0]

def test_double_raw_string_literal():
    yield check_token, 'r"yo"', ['STRING', 'r"yo"', 0]

def test_single_unicode_literal():
    yield check_token, "u'yo'", ['STRING', "u'yo'", 0]

def test_double_unicode_literal():
    yield check_token, 'u"yo"', ['STRING', 'u"yo"', 0]

def test_single_bytes_literal():
    yield check_token, "b'yo'", ['STRING', "b'yo'", 0]

def test_float_literals():
    cases = ['0.0', '.0', '0.', '1e10', '1.e42', '0.1e42', '0.5e-42',
             '5E10', '5e+42']
    for s in cases:
        yield check_token, s, ['NUMBER', s, 0]

def test_ioredir():
    cases = ['2>1', 'err>out', 'o>', 'all>', 'e>o', 'e>', 'out>', '2>&1']
    for s in cases:
        yield check_tokens_subproc, s, [('IOREDIRECT', s, 2)]


if __name__ == '__main__':
    nose.runmodule()
