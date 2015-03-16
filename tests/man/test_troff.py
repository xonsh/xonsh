"""Tests the troff lexer and parser."""
from __future__ import unicode_literals, print_function
import os
import sys
from collections import Sequence

from nose.tools import assert_equal, assert_true

from ply.lex import LexToken

from xonsh.man.troff import TroffLexer

LEXER = TroffLexer()
LEXER.build(lextab='troff_test_lexer')

def ensure_tuple(x):
    if isinstance(x, LexToken):
        # line numbers can no longer be solely determined from the lexer
        x = (x.type, x.value, x.lineno, x.lexpos)
        #x = (x.type, x.value, x.lexpos)
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
    LEXER.reset()
    LEXER.input(input)
    obs = list(LEXER)
    if len(obs) != 1:
        msg = 'The observed sequence does not have length-1: {0!r} != 1\n'
        msg += '# obs\n{1}'
        raise AssertionError(msg.format(len(obs), pformat(obs)))
    assert_token_equal(exp, obs[0])

def check_tokens(input, exp):
    LEXER.reset()
    LEXER.input(input)
    obs = list(LEXER)
    assert_tokens_equal(exp, obs)


def test_newline():
    input = '\n'
    check_token(input, ['NEWLINE', input, 1, 0])

def test_comment():
    input = '.\\" I am a comment'
    check_token(input, ['COMMENT', input, 1, 0])

def test_endmarker():
    input = '\x03'
    check_token(input, ['ENDMARKER', input, 1, 0])

def test_space():
    input = ' '
    check_token(input, ['SPACE', input, 1, 0])

def test_title():
    input = '.TH'
    check_token(input, ['TITLE', input, 1, 0])

def test_section():
    input = '.SH'
    check_token(input, ['SECTION', input, 1, 0])

def test_subsection():
    input = '.SS'
    check_token(input, ['SUBSECTION', input, 1, 0])

def test_paragraph():
    input = '.P'
    check_token(input, ['PARAGRAPH', input, 1, 0])

def test_hanging_paragraph():
    input = '.HP'
    check_token(input, ['HANGING_PARAGRAPH', input, 1, 0])

def test_indent_start():
    input = '.RS'
    check_token(input, ['INDENT_START', input, 1, 0])

def test_indent_end():
    input = '.RE'
    check_token(input, ['INDENT_END', input, 1, 0])

def test_word():
    input = 'wakka'
    check_token(input, ['WORD', input, 1, 0])

def test_italics():
    input = '.I'
    check_token(input, ['ITALICS', input, 1, 0])

def test_bold():
    input = '.B'
    check_token(input, ['BOLD', input, 1, 0])



if __name__ == '__main__':
    nose.runmodule()
