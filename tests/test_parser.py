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
#DEBUG_LEVEL = 100

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

def test_binop_plus():
    yield check_ast, '42 + 65'

def test_binop_minus():
    yield check_ast, '42 - 65'

def test_binop_times():
    yield check_ast, '42 * 65'

def test_binop_div():
    yield check_ast, '42 / 65'

def test_binop_mod():
    yield check_ast, '42 % 65'

def test_binop_floordiv():
    yield check_ast, '42 // 65'

def test_binop_pow():
    yield check_ast, '2 ** 2'

def test_plus_pow():
    yield check_ast, '42 + 2 ** 2'

def test_plus_plus():
    yield check_ast, '42 + 65 + 6'

def test_plus_minus():
    yield check_ast, '42 + 65 - 6'

def test_minus_plus():
    yield check_ast, '42 - 65 + 6'

def test_minus_minus():
    yield check_ast, '42 - 65 - 6'

def test_minus_plus_minus():
    yield check_ast, '42 - 65 + 6 - 28'

def test_times_plus():
    yield check_ast, '42 * 65 + 6'

def test_plus_times():
    yield check_ast, '42 + 65 * 6'

def test_times_times():
    yield check_ast, '42 * 65 * 6'

def test_times_div():
    yield check_ast, '42 * 65 / 6'

def test_times_div_mod():
    yield check_ast, '42 * 65 / 6 % 28'

def test_times_div_mod_floor():
    yield check_ast, '42 * 65 / 6 % 28 // 13'

def test_str_str():
    yield check_ast, '"hello" \'mom\''

def test_str_plus_str():
    yield check_ast, '"hello" + \'mom\''

def test_str_times_int():
    yield check_ast, '"hello" * 20'

def test_int_times_str():
    yield check_ast, '2*"hello"'

def test_group_plus_times():
    yield check_ast, '(42 + 65) * 20'

def test_plus_group_times():
    yield check_ast, '42 + (65 * 20)'

def test_group():
    yield check_ast, '(42)'

def test_lt():
    yield check_ast, '42 < 65'

def test_lt():
    yield check_ast, '42 < 65'

def test_gt():
    yield check_ast, '42 > 65'

def test_eq():
    yield check_ast, '42 == 65'

def test_lt():
    yield check_ast, '42 < 65'

def test_le():
    yield check_ast, '42 <= 65'

def test_ge():
    yield check_ast, '42 >= 65'

def test_ne():
    yield check_ast, '42 != 65'

def test_in():
    yield check_ast, '"4" in "65"'

def test_is():
    yield check_ast, '42 is 65'

def test_not_in():
    yield check_ast, '"4" not in "65"'

def test_is_not():
    yield check_ast, '42 is not 65'

def test_lt_lt():
    yield check_ast, '42 < 65 < 105'

def test_lt_lt_lt():
    yield check_ast, '42 < 65 < 105 < 77'

def test_not():
    yield check_ast, 'not 0'

def test_or():
    yield check_ast, '1 or 0'

def test_or_or():
    yield check_ast, '1 or 0 or 42'

def test_and():
    yield check_ast, '1 and 0'

def test_and_and():
    yield check_ast, '1 and 0 and 2'

def test_and_or():
    yield check_ast, '1 and 0 or 2'

def test_or_and():
    yield check_ast, '1 or 0 and 2'

def test_group_and_and():
    yield check_ast, '(1 and 0) and 2'

def test_group_and_or():
    yield check_ast, '(1 and 0) or 2'

def test_str_idx():
    yield check_ast, '"hello"[0]'

def test_str_slice():
    yield check_ast, '"hello"[0:3]'

def test_str_step():
    yield check_ast, '"hello"[0:3:1]'

def test_str_slice_all():
    yield check_ast, '"hello"[:]'

def test_str_slice_upper():
    yield check_ast, '"hello"[5:]'

def test_str_slice_lower():
    yield check_ast, '"hello"[:3]'

def test_str_slice_other():
    yield check_ast, '"hello"[::2]'

def test_str_slice_lower_other():
    yield check_ast, '"hello"[:3:2]'

def test_str_slice_upper_other():
    yield check_ast, '"hello"[3::2]'

def test_list_empty():
    yield check_ast, '[]'

def test_list_one():
    yield check_ast, '[1]'

def test_list_one_comma():
    yield check_ast, '[1,]'

def test_list_one_comma():
    yield check_ast, '[1,]'

def test_list_two():
    yield check_ast, '[1, 42]'

def test_list_one_comma():
    yield check_ast, '[1,]'

def test_list_three():
    yield check_ast, '[1, 42, 65]'

def test_list_three():
    yield check_ast, '[1, 42, 65,]'

#DEBUG_LEVEL = 100









 

if __name__ == '__main__':
    nose.runmodule()
