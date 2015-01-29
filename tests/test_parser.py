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
assert_equal.__self__.maxDiff = None

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

def check_ast(input, run=True):
    # expect a Python AST
    exp = ast.parse(input)
    # observe something from xonsh
    obs = PARSER.parse(input, debug_level=DEBUG_LEVEL)
    # Check that they are equal
    assert_nodes_equal(exp, obs)
    # round trip by running xonsh AST via Python
    if run:
        exec(compile(obs, '<test>', 'exec'))

def check_stmts(input, run=True):
    if not input.endswith('\n'):
        input += '\n'
    check_ast(input, run=run)

#
# Tests
#

#
# expressions
#

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

def test_if_else_expr():
    yield check_ast, '42 if True else 65'

def test_if_else_expr():
    yield check_ast, '42+5 if 1 == 2 else 65-5'

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

def test_list_two():
    yield check_ast, '[1, 42]'

def test_list_three():
    yield check_ast, '[1, 42, 65]'

def test_list_three():
    yield check_ast, '[1, 42, 65,]'

def test_tuple_empty():
    yield check_ast, '()'

def test_tuple_one_bare():
    yield check_ast, '1,'

def test_tuple_two_bare():
    yield check_ast, '1, 42'

def test_tuple_three_bare():
    yield check_ast, '1, 42, 65'

def test_tuple_three_bare_comma():
    yield check_ast, '1, 42, 65,'

def test_tuple_one_comma():
    yield check_ast, '(1,)'

def test_tuple_two():
    yield check_ast, '(1, 42)'

def test_tuple_three():
    yield check_ast, '(1, 42, 65)'

def test_tuple_three():
    yield check_ast, '(1, 42, 65,)'

def test_set_one():
    yield check_ast, '{42}'

def test_set_one_comma():
    yield check_ast, '{42,}'

def test_set_two():
    yield check_ast, '{42, 65}'

def test_set_two_comma():
    yield check_ast, '{42, 65,}'

def test_set_three():
    yield check_ast, '{42, 65, 45}'

def test_dict_empty():
    yield check_ast, '{}'

def test_dict_one():
    yield check_ast, '{42: 65}'

def test_dict_one_comma():
    yield check_ast, '{42: 65,}'

def test_dict_two():
    yield check_ast, '{42: 65, 6: 28}'

def test_dict_two_comma():
    yield check_ast, '{42: 65, 6: 28,}'

def test_dict_three():
    yield check_ast, '{42: 65, 6: 28, 1: 2}'

def test_true():
    yield check_ast, 'True'

def test_false():
    yield check_ast, 'False'

def test_none():
    yield check_ast, 'None'

def test_elipssis():
    yield check_ast, '...'

def test_not_implemented_name():
    yield check_ast, 'NotImplemented'

def test_genexpr():
    yield check_ast, '(x for x in "mom")'

def test_genexpr_if():
    yield check_ast, '(x for x in "mom" if True)'

def test_genexpr_if_and():
    yield check_ast, '(x for x in "mom" if True and x == "m")'

def test_dbl_genexpr():
    yield check_ast, '(x+y for x in "mom" for y in "dad")'

def test_genexpr_if_genexpr():
    yield check_ast, '(x+y for x in "mom" if True for y in "dad")'

def test_genexpr_if_genexpr_if():
    yield check_ast, '(x+y for x in "mom" if True for y in "dad" if y == "d")'

def test_listcomp():
    yield check_ast, '[x for x in "mom"]'

def test_listcomp_if():
    yield check_ast, '[x for x in "mom" if True]'

def test_listcomp_if_and():
    yield check_ast, '[x for x in "mom" if True and x == "m"]'

def test_dbl_listcomp():
    yield check_ast, '[x+y for x in "mom" for y in "dad"]'

def test_listcomp_if_listcomp():
    yield check_ast, '[x+y for x in "mom" if True for y in "dad"]'

def test_listcomp_if_listcomp_if():
    yield check_ast, '[x+y for x in "mom" if True for y in "dad" if y == "d"]'

def test_setcomp():
    yield check_ast, '{x for x in "mom"}'

def test_setcomp_if():
    yield check_ast, '{x for x in "mom" if True}'

def test_setcomp_if_and():
    yield check_ast, '{x for x in "mom" if True and x == "m"}'

def test_dbl_setcomp():
    yield check_ast, '{x+y for x in "mom" for y in "dad"}'

def test_setcomp_if_setcomp():
    yield check_ast, '{x+y for x in "mom" if True for y in "dad"}'

def test_setcomp_if_setcomp_if():
    yield check_ast, '{x+y for x in "mom" if True for y in "dad" if y == "d"}'

def test_dictcomp():
    yield check_ast, '{x: x for x in "mom"}'

def test_dictcomp_if():
    yield check_ast, '{x:x for x in "mom" if True}'

def test_dictcomp_if_and():
    yield check_ast, '{x:x for x in "mom" if True and x == "m"}'

def test_dbl_dictcomp():
    yield check_ast, '{x:y for x in "mom" for y in "dad"}'

def test_dictcomp_if_dictcomp():
    yield check_ast, '{x:y for x in "mom" if True for y in "dad"}'

def test_dictcomp_if_dictcomp_if():
    yield check_ast, '{x:y for x in "mom" if True for y in "dad" if y == "d"}'

def test_lambda():
    yield check_ast, 'lambda: 42'

def test_lambda_x():
    yield check_ast, 'lambda x: x'

def test_lambda_kwx():
    yield check_ast, 'lambda x=42: x'

def test_lambda_x_y():
    yield check_ast, 'lambda x, y: x'

def test_lambda_x_y():
    yield check_ast, 'lambda x, y: x'

def test_lambda_x_y_z():
    yield check_ast, 'lambda x, y, z: x'

def test_lambda_x_y():
    yield check_ast, 'lambda x, y: x'

def test_lambda_x_kwy():
    yield check_ast, 'lambda x, y=42: x'

def test_lambda_kwx_kwy():
    yield check_ast, 'lambda x=65, y=42: x'

def test_lambda_kwx_kwy_kwz():
    yield check_ast, 'lambda x=65, y=42, z=1: x'

def test_lambda_x_comma():
    yield check_ast, 'lambda x,: x'

def test_lambda_x_y_comma():
    yield check_ast, 'lambda x, y,: x'

def test_lambda_x_y_z_comma():
    yield check_ast, 'lambda x, y, z,: x'

def test_lambda_x_y_comma():
    yield check_ast, 'lambda x, y,: x'

def test_lambda_x_kwy_comma():
    yield check_ast, 'lambda x, y=42,: x'

def test_lambda_kwx_kwy_comma():
    yield check_ast, 'lambda x=65, y=42,: x'

def test_lambda_kwx_kwy_kwz_comma():
    yield check_ast, 'lambda x=65, y=42, z=1,: x'

def test_lambda_args():
    yield check_ast, 'lambda *args: 42'

def test_lambda_args_x():
    yield check_ast, 'lambda *args, x: 42'

def test_lambda_args_x_y():
    yield check_ast, 'lambda *args, x, y: 42'

def test_lambda_args_x_kwy():
    yield check_ast, 'lambda *args, x, y=10: 42'

def test_lambda_args_kwx_y():
    yield check_ast, 'lambda *args, x=10, y: 42'

def test_lambda_args_kwx_kwy():
    yield check_ast, 'lambda *args, x=42, y=65: 42'

def test_lambda_x_args():
    yield check_ast, 'lambda x, *args: 42'

def test_lambda_x_args_y():
    yield check_ast, 'lambda x, *args, y: 42'

def test_lambda_x_args_y_z():
    yield check_ast, 'lambda x, *args, y, z: 42'

def test_lambda_kwargs():
    yield check_ast, 'lambda **kwargs: 42'

def test_lambda_x_kwargs():
    yield check_ast, 'lambda x, **kwargs: 42'

def test_lambda_x_y_kwargs():
    yield check_ast, 'lambda x, y, **kwargs: 42'

def test_lambda_x_kwy_kwargs():
    yield check_ast, 'lambda x, y=42, **kwargs: 42'

def test_lambda_args_kwargs():
    yield check_ast, 'lambda *args, **kwargs: 42'

def test_lambda_x_args_kwargs():
    yield check_ast, 'lambda x, *args, **kwargs: 42'

def test_lambda_x_y_args_kwargs():
    yield check_ast, 'lambda x, y, *args, **kwargs: 42'

def test_lambda_kwx_args_kwargs():
    yield check_ast, 'lambda x=10, *args, **kwargs: 42'

def test_lambda_x_kwy_args_kwargs():
    yield check_ast, 'lambda x, y=42, *args, **kwargs: 42'

def test_lambda_x_args_y_kwargs():
    yield check_ast, 'lambda x, *args, y, **kwargs: 42'

def test_lambda_x_args_kwy_kwargs():
    yield check_ast, 'lambda x, *args, y=42, **kwargs: 42'

def test_lambda_args_y_kwargs():
    yield check_ast, 'lambda *args, y, **kwargs: 42'

def test_lambda_star_x():
    yield check_ast, 'lambda *, x: 42'

def test_lambda_star_x_y():
    yield check_ast, 'lambda *, x, y: 42'

def test_lambda_star_x_kwargs():
    yield check_ast, 'lambda *, x, **kwargs: 42'

def test_lambda_star_kwx_kwargs():
    yield check_ast, 'lambda *, x=42, **kwargs: 42'

def test_lambda_x_star_y():
    yield check_ast, 'lambda x, *, y: 42'

def test_lambda_x_y_star_z():
    yield check_ast, 'lambda x, y, *, z: 42'

def test_lambda_x_kwy_star_y():
    yield check_ast, 'lambda x, y=42, *, z: 42'

def test_lambda_x_kwy_star_kwy():
    yield check_ast, 'lambda x, y=42, *, z=65: 42'

def test_lambda_x_star_y_kwargs():
    yield check_ast, 'lambda x, *, y, **kwargs: 42'

def test_call_range():
    yield check_ast, 'range(6)'

def test_call_range_comma():
    yield check_ast, 'range(6,)'

def test_call_range_x_y():
    yield check_ast, 'range(6, 10)'

def test_call_range_x_y():
    yield check_ast, 'range(6, 10)'

def test_call_range_x_y():
    yield check_ast, 'range(6, 10)'

def test_call_range_x_y_comma():
    yield check_ast, 'range(6, 10,)'

def test_call_range_x_y_z():
    yield check_ast, 'range(6, 10, 2)'

def test_call_range_x_y():
    yield check_ast, 'range(6, 10)'

def test_call_dict_kwx():
    yield check_ast, 'dict(start=10)'

def test_call_dict_kwx_comma():
    yield check_ast, 'dict(start=10,)'

def test_call_dict_kwx_kwy():
    yield check_ast, 'dict(start=10, stop=42)'

def test_call_tuple_gen():
    yield check_ast, 'tuple(x for x in [1, 2, 3])'

def test_call_tuple_genifs():
    yield check_ast, 'tuple(x for x in [1, 2, 3] if x < 3)'

def test_call_range_star():
    yield check_ast, 'range(*[1, 2, 3])'

def test_call_range_x_star():
    yield check_ast, 'range(1, *[2, 3])'

def test_call_int():
    yield check_ast, 'int(*["42"], base=8)'

def test_call_int_base_dict():
    yield check_ast, 'int(*["42"], **{"base": 8})'

def test_call_int_base_dict():
    yield check_ast, 'int(*["42"], **{"base": 8})'

def test_call_dict_kwargs():
    yield check_ast, 'dict(**{"base": 8})'

def test_call_alot():
    yield check_ast, 'x(1, *args, **kwargs)', False

def test_call_alot_next():
    yield check_ast, 'x(x=1, *args, **kwargs)', False

def test_call_alot_next_next():
    yield check_ast, 'x(x=1, *args, y=42, **kwargs)', False

def test_getattr():
    yield check_ast, 'list.append'

def test_getattr_getattr():
    yield check_ast, 'list.append.__str__'





#DEBUG_LEVEL = 1




#
# statements
#

def test_equals():
    yield check_stmts, 'x = 42'

def test_equals_semi():
    yield check_stmts, 'x = 42;'

def test_equals_two():
    yield check_stmts, 'x = 42; y = 65'

def test_equals_two_semi():
    yield check_stmts, 'x = 42; y = 65;'

def test_equals_three():
    yield check_stmts, 'x = 42; y = 65; z = 6'

def test_equals_three_semi():
    yield check_stmts, 'x = 42; y = 65; z = 6;'

def test_plus_eq():
    yield check_stmts, 'x = 42; x += 65'

def test_sub_eq():
    yield check_stmts, 'x = 42; x -= 2'

def test_times_eq():
    yield check_stmts, 'x = 42; x *= 2'

def test_div_eq():
    yield check_stmts, 'x = 42; x /= 2'

def test_floordiv_eq():
    yield check_stmts, 'x = 42; x //= 2'

def test_pow_eq():
    yield check_stmts, 'x = 42; x **= 2'

def test_mod_eq():
    yield check_stmts, 'x = 42; x %= 2'

def test_xor_eq():
    yield check_stmts, 'x = 42; x ^= 2'

def test_ampersand_eq():
    yield check_stmts, 'x = 42; x &= 2'

def test_bitor_eq():
    yield check_stmts, 'x = 42; x |= 2'

def test_lshift_eq():
    yield check_stmts, 'x = 42; x <<= 2'

def test_rshift_eq():
    yield check_stmts, 'x = 42; x >>= 2'

def test_assert():
    yield check_stmts, 'assert True'

def test_assert():
    yield check_stmts, 'assert True'

def test_assert_msg():
    yield check_stmts, 'assert True, "wow mom"'

def test_assert():
    yield check_stmts, 'assert True'

def test_pass():
    yield check_stmts, 'pass'

def test_del():
    yield check_stmts, 'x = 42; del x'

def test_del_comma():
    yield check_stmts, 'x = 42; del x,'

def test_del_two():
    yield check_stmts, 'x = 42; y = 65; del x, y'

def test_del_two_comma():
    yield check_stmts, 'x = 42; y = 65; del x, y,'

def test_raise():
    yield check_stmts, 'raise', False
    
def test_raise_x():
    yield check_stmts, 'raise TypeError', False
    
def test_raise_x_from():
    yield check_stmts, 'raise TypeError from x', False

def test_import_x():
    yield check_stmts, 'import x', False

def test_import_xy():
    yield check_stmts, 'import x.y', False

def test_import_xyz():
    yield check_stmts, 'import x.y.z', False

def test_from_x_import_y():
    yield check_stmts, 'from x import y', False
    
def test_from_dot_import_y():
    yield check_stmts, 'from . import y', False
    
def test_from_dotx_import_y():
    yield check_stmts, 'from .x import y', False
    
def test_from_dotdotx_import_y():
    yield check_stmts, 'from ..x import y', False

def test_from_dotdotdotx_import_y():
    yield check_stmts, 'from ...x import y', False

def test_from_dotdotdotdotx_import_y():
    yield check_stmts, 'from ....x import y', False

def test_from_import_x_y():
    yield check_stmts, 'import x, y', False

def test_from_import_x_y_z():
    yield check_stmts, 'import x, y, z', False

def test_from_dot_import_x_y():
    yield check_stmts, 'from . import x, y', False
    
def test_from_dot_import_x_y():
    yield check_stmts, 'from . import x, y', False
    
def test_from_dot_import_x_y_z():
    yield check_stmts, 'from . import x, y, z', False

def test_from_dot_import_x_y():
    yield check_stmts, 'from . import x, y', False
    
def test_from_dot_import_group_x_y():
    yield check_stmts, 'from . import (x, y)', False

def test_import_x_as_y():
    yield check_stmts, 'import x as y', False

def test_import_xy_as_z():
    yield check_stmts, 'import x.y as z', False

def test_import_x_y_as_z():
    yield check_stmts, 'import x, y as z', False

def test_import_x_as_y_z():
    yield check_stmts, 'import x as y, z', False

def test_import_x_as_y_z_as_a():
    yield check_stmts, 'import x as y, z as a', False

def test_from_dot_import_x_as_y():
    yield check_stmts, 'from . import x as y', False

def test_from_x_import_y_as_z():
    yield check_stmts, 'from x import y as z', False

def test_from_x_import_y_as_z_a_as_b():
    yield check_stmts, 'from x import y as z, a as b', False

def test_from_dotx_import_y_as_z_a_as_b_c_as_d():
    yield check_stmts, 'from .x import y as z, a as b, c as d', False

def test_continue():
    yield check_stmts, 'continue', False

def test_break():
    yield check_stmts, 'break', False

def test_global():
    yield check_stmts, 'global x', False

def test_global_xy():
    yield check_stmts, 'global x, y', False

def test_nonlocal_x():
    yield check_stmts, 'nonlocal x', False

def test_nonlocal_xy():
    yield check_stmts, 'nonlocal x, y', False

def test_yield():
    yield check_stmts, 'yield', False

def test_yield_x():
    yield check_stmts, 'yield x', False

def test_yield_x_comma():
    yield check_stmts, 'yield x,', False

def test_yield_x_y():
    yield check_stmts, 'yield x, y', False

def test_yield_from_x():
    yield check_stmts, 'yield from x', False

def test_return():
    yield check_stmts, 'return', False

def test_return_x():
    yield check_stmts, 'return x', False

def test_return_x_comma():
    yield check_stmts, 'return x,', False

def test_return_x_y():
    yield check_stmts, 'return x, y', False





#DEBUG_LEVEL = 1
#DEBUG_LEVEL = 100









 

if __name__ == '__main__':
    nose.runmodule()
