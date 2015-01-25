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

def nodes_equal(x, y):
    if type(x) != type(y):
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
    exp = ast.parse(input)
    p = Parser(lexer_optimize=False, yacc_optimize=False, yacc_debug=True)
    obs = p.parse(input, debug_level=100)
    assert_nodes_equal(exp, obs)


def test_int_literal():
    yield check_ast, '42'


if __name__ == '__main__':
    nose.runmodule()