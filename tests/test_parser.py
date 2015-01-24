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

from xonsh.parser import Parser


def check_ast(input, exp):
    p = Parser(lexer_optimize=False, yacc_optimize=False, yacc_debug=True)
    obs = p.parse(input)
    assert_equal(exp, obs)


def test_int_literal():
    yield check_ast, '42', ['INT_LITERAL', '42', 1, 0]



if __name__ == '__main__':
    nose.runmodule()