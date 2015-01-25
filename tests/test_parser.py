"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os
import sys
import ast
from collections import Sequence
from pprint import pprint, pformat
sys.path.insert(0, os.path.abspath('..'))  # FIXME

import nose
from nose.tools import assert_equal

from ply.lex import LexToken

from xonsh.parser import Parser

PARSER = None
DEBUG_LEVEL = 0

def setup():
    # only setup one parser
    global PARSER
    PARSER = Parser(lexer_optimize=False, yacc_optimize=False, yacc_debug=True)

def nodes_equal(x, y):
    if type(x) != type(y):
        return False
    if isinstance(x, ast.Expr):
        if x.lineno != y.lineno:
            return False
        if x.col_offset != y.col_offset:
            return False
    for (xname, xval), (yname, yval) in zip(ast.iter_fields(x), 
                                            ast.iter_fields(y)):
        if xname != yname:
            return False
        if xval != yval:
            return False
    for xchild, ychild in zip(ast.iter_child_nodes(x), 
                              ast.iter_child_nodes(y)):
        if not nodes_equal(xchild, ychild):
            return False
    return True

def assert_nodes_equal(x, y):
    if nodes_equal(x, y):
        return True
    assert_equal(ast.dump(x), ast.dump(y))

def check_ast(input):
    # expect a Python AST
    exp = ast.parse(input)
    # observe something from xonsh
    obs = PARSER.parse(input, debug_level=DEBUG_LEVEL)
    # Check that they are equal
    assert_nodes_equal(exp, obs)
    # round trip by running xonsh AST via Python
    exec(compile(obs, '<test>', 'exec'))


def test_int_literal():
    yield check_ast, '42'

def test_float_literal():
    yield check_ast, '42.0'

def test_str_literal():
    yield check_ast, '"hello"'

def test_bytes_literal():
    yield check_ast, 'b"hello"'

def test_unary_plus():
    yield check_ast, '+1'

def test_unary_minus():
    yield check_ast, '-1'

def test_unary_invert():
    yield check_ast, '~1'





if __name__ == '__main__':
    nose.runmodule()