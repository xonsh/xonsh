# -*- coding: utf-8 -*-
"""Tests the xonsh parser."""
import ast
import builtins
import textwrap
import itertools

import pytest

from xonsh.ast import AST, With, Pass, pdump
from xonsh.parser import Parser
from xonsh.parsers.base import eval_fstr_fields

from tools import VER_FULL, skip_if_py34, skip_if_lt_py36, nodes_equal

# a lot of col_offset data changed from Py v3.5.0 -> v3.5.1
INC_ATTRS = (3, 5, 1) <= VER_FULL


@pytest.fixture(autouse=True)
def xonsh_builtins_autouse(xonsh_builtins):
    return xonsh_builtins


PARSER = Parser(lexer_optimize=False, yacc_optimize=False, yacc_debug=True)


def check_ast(inp, run=True, mode="eval", debug_level=0):
    __tracebackhide__ = True
    # expect a Python AST
    exp = ast.parse(inp, mode=mode)
    # observe something from xonsh
    obs = PARSER.parse(inp, debug_level=debug_level)
    # Check that they are equal
    assert nodes_equal(exp, obs)
    # round trip by running xonsh AST via Python
    if run:
        exec(compile(obs, "<test-ast>", mode))


def check_stmts(inp, run=True, mode="exec", debug_level=0):
    __tracebackhide__ = True
    if not inp.endswith("\n"):
        inp += "\n"
    check_ast(inp, run=run, mode=mode, debug_level=debug_level)


def check_xonsh_ast(xenv, inp, run=True, mode="eval", debug_level=0, return_obs=False):
    __tracebackhide__ = True
    builtins.__xonsh__.env = xenv
    obs = PARSER.parse(inp, debug_level=debug_level)
    if obs is None:
        return  # comment only
    bytecode = compile(obs, "<test-xonsh-ast>", mode)
    if run:
        exec(bytecode)
    return obs if return_obs else True


def check_xonsh(xenv, inp, run=True, mode="exec"):
    __tracebackhide__ = True
    if not inp.endswith("\n"):
        inp += "\n"
    check_xonsh_ast(xenv, inp, run=run, mode=mode)


#
# Tests
#

#
# expressions
#


def test_int_literal():
    check_ast("42")


@skip_if_lt_py36
def test_int_literal_underscore():
    check_ast("4_2")


def test_float_literal():
    check_ast("42.0")


@skip_if_lt_py36
def test_float_literal_underscore():
    check_ast("4_2.4_2")


def test_imag_literal():
    check_ast("42j")


def test_float_imag_literal():
    check_ast("42.0j")


def test_complex():
    check_ast("42+84j")


def test_str_literal():
    check_ast('"hello"')


def test_bytes_literal():
    check_ast('b"hello"')
    check_ast('B"hello"')


def test_raw_literal():
    check_ast('r"hell\\o"')
    check_ast('R"hell\\o"')


@skip_if_lt_py36
def test_f_literal():
    check_ast('f"wakka{yo}yakka{42}"', run=False)
    check_ast('F"{yo}"', run=False)


@skip_if_lt_py36
def test_f_env_var():
    check_xonsh_ast({}, 'f"{$HOME}"', run=False)
    check_xonsh_ast({}, "f'{$XONSH_DEBUG}'", run=False)
    check_xonsh_ast({}, 'F"{$PATH} and {$XONSH_DEBUG}"', run=False)


@pytest.mark.parametrize(
    "inp, exp",
    [
        ('f"{}"', 'f"{}"'),
        ('f"$HOME"', 'f"$HOME"'),
        ('f"{0} - {1}"', 'f"{0} - {1}"'),
        (
            'f"{$HOME}"',
            "f\"{__xonsh__.execer.eval(r'$HOME', glbs=globals(), locs=locals())}\"",
        ),
        (
            'f"{ $HOME }"',
            "f\"{__xonsh__.execer.eval(r'$HOME ', glbs=globals(), locs=locals())}\"",
        ),
        (
            "f\"{'$HOME'}\"",
            "f\"{__xonsh__.execer.eval(r'\\'$HOME\\'', glbs=globals(), locs=locals())}\"",
        ),
    ],
)
def test_eval_fstr_fields(inp, exp):
    obs = eval_fstr_fields(inp, 'f"')
    assert exp == obs


def test_raw_bytes_literal():
    check_ast('br"hell\\o"')
    check_ast('RB"hell\\o"')
    check_ast('Br"hell\\o"')
    check_ast('rB"hell\\o"')


def test_unary_plus():
    check_ast("+1")


def test_unary_minus():
    check_ast("-1")


def test_unary_invert():
    check_ast("~1")


def test_binop_plus():
    check_ast("42 + 65")


def test_binop_minus():
    check_ast("42 - 65")


def test_binop_times():
    check_ast("42 * 65")


@skip_if_py34
def test_binop_matmult():
    check_ast("x @ y", False)


def test_binop_div():
    check_ast("42 / 65")


def test_binop_mod():
    check_ast("42 % 65")


def test_binop_floordiv():
    check_ast("42 // 65")


def test_binop_pow():
    check_ast("2 ** 2")


def test_plus_pow():
    check_ast("42 + 2 ** 2")


def test_plus_plus():
    check_ast("42 + 65 + 6")


def test_plus_minus():
    check_ast("42 + 65 - 6")


def test_minus_plus():
    check_ast("42 - 65 + 6")


def test_minus_minus():
    check_ast("42 - 65 - 6")


def test_minus_plus_minus():
    check_ast("42 - 65 + 6 - 28")


def test_times_plus():
    check_ast("42 * 65 + 6")


def test_plus_times():
    check_ast("42 + 65 * 6")


def test_times_times():
    check_ast("42 * 65 * 6")


def test_times_div():
    check_ast("42 * 65 / 6")


def test_times_div_mod():
    check_ast("42 * 65 / 6 % 28")


def test_times_div_mod_floor():
    check_ast("42 * 65 / 6 % 28 // 13")


def test_str_str():
    check_ast("\"hello\" 'mom'")


def test_str_str_str():
    check_ast('"hello" \'mom\'    "wow"')


def test_str_plus_str():
    check_ast("\"hello\" + 'mom'")


def test_str_times_int():
    check_ast('"hello" * 20')


def test_int_times_str():
    check_ast('2*"hello"')


def test_group_plus_times():
    check_ast("(42 + 65) * 20")


def test_plus_group_times():
    check_ast("42 + (65 * 20)")


def test_group():
    check_ast("(42)")


def test_lt():
    check_ast("42 < 65")


def test_gt():
    check_ast("42 > 65")


def test_eq():
    check_ast("42 == 65")


def test_le():
    check_ast("42 <= 65")


def test_ge():
    check_ast("42 >= 65")


def test_ne():
    check_ast("42 != 65")


def test_in():
    check_ast('"4" in "65"')


def test_is():
    check_ast("42 is 65")


def test_not_in():
    check_ast('"4" not in "65"')


def test_is_not():
    check_ast("42 is not 65")


def test_lt_lt():
    check_ast("42 < 65 < 105")


def test_lt_lt_lt():
    check_ast("42 < 65 < 105 < 77")


def test_not():
    check_ast("not 0")


def test_or():
    check_ast("1 or 0")


def test_or_or():
    check_ast("1 or 0 or 42")


def test_and():
    check_ast("1 and 0")


def test_and_and():
    check_ast("1 and 0 and 2")


def test_and_or():
    check_ast("1 and 0 or 2")


def test_or_and():
    check_ast("1 or 0 and 2")


def test_group_and_and():
    check_ast("(1 and 0) and 2")


def test_group_and_or():
    check_ast("(1 and 0) or 2")


def test_if_else_expr():
    check_ast("42 if True else 65")


def test_if_else_expr_expr():
    check_ast("42+5 if 1 == 2 else 65-5")


def test_str_idx():
    check_ast('"hello"[0]')


def test_str_slice():
    check_ast('"hello"[0:3]')


def test_str_step():
    check_ast('"hello"[0:3:1]')


def test_str_slice_all():
    check_ast('"hello"[:]')


def test_str_slice_upper():
    check_ast('"hello"[5:]')


def test_str_slice_lower():
    check_ast('"hello"[:3]')


def test_str_slice_other():
    check_ast('"hello"[::2]')


def test_str_slice_lower_other():
    check_ast('"hello"[:3:2]')


def test_str_slice_upper_other():
    check_ast('"hello"[3::2]')


def test_str_2slice():
    check_ast('"hello"[0:3,0:3]', False)


def test_str_2step():
    check_ast('"hello"[0:3:1,0:4:2]', False)


def test_str_2slice_all():
    check_ast('"hello"[:,:]', False)


def test_str_2slice_upper():
    check_ast('"hello"[5:,5:]', False)


def test_str_2slice_lower():
    check_ast('"hello"[:3,:3]', False)


def test_str_2slice_lowerupper():
    check_ast('"hello"[5:,:3]', False)


def test_str_2slice_other():
    check_ast('"hello"[::2,::2]', False)


def test_str_2slice_lower_other():
    check_ast('"hello"[:3:2,:3:2]', False)


def test_str_2slice_upper_other():
    check_ast('"hello"[3::2,3::2]', False)


def test_str_3slice():
    check_ast('"hello"[0:3,0:3,0:3]', False)


def test_str_3step():
    check_ast('"hello"[0:3:1,0:4:2,1:3:2]', False)


def test_str_3slice_all():
    check_ast('"hello"[:,:,:]', False)


def test_str_3slice_upper():
    check_ast('"hello"[5:,5:,5:]', False)


def test_str_3slice_lower():
    check_ast('"hello"[:3,:3,:3]', False)


def test_str_3slice_lowerlowerupper():
    check_ast('"hello"[:3,:3,:3]', False)


def test_str_3slice_lowerupperlower():
    check_ast('"hello"[:3,5:,:3]', False)


def test_str_3slice_lowerupperupper():
    check_ast('"hello"[:3,5:,5:]', False)


def test_str_3slice_upperlowerlower():
    check_ast('"hello"[5:,5:,:3]', False)


def test_str_3slice_upperlowerupper():
    check_ast('"hello"[5:,:3,5:]', False)


def test_str_3slice_upperupperlower():
    check_ast('"hello"[5:,5:,:3]', False)


def test_str_3slice_other():
    check_ast('"hello"[::2,::2,::2]', False)


def test_str_3slice_lower_other():
    check_ast('"hello"[:3:2,:3:2,:3:2]', False)


def test_str_3slice_upper_other():
    check_ast('"hello"[3::2,3::2,3::2]', False)


def test_str_slice_true():
    check_ast('"hello"[0:3,True]', False)


def test_str_true_slice():
    check_ast('"hello"[True,0:3]', False)


def test_list_empty():
    check_ast("[]")


def test_list_one():
    check_ast("[1]")


def test_list_one_comma():
    check_ast("[1,]")


def test_list_two():
    check_ast("[1, 42]")


def test_list_three():
    check_ast("[1, 42, 65]")


def test_list_three_comma():
    check_ast("[1, 42, 65,]")


def test_list_one_nested():
    check_ast("[[1]]")


def test_list_list_four_nested():
    check_ast("[[1], [2], [3], [4]]")


def test_list_tuple_three_nested():
    check_ast("[(1,), (2,), (3,)]")


def test_list_set_tuple_three_nested():
    check_ast("[{(1,)}, {(2,)}, {(3,)}]")


def test_list_tuple_one_nested():
    check_ast("[(1,)]")


def test_tuple_tuple_one_nested():
    check_ast("((1,),)")


def test_dict_list_one_nested():
    check_ast("{1: [2]}")


def test_dict_list_one_nested_comma():
    check_ast("{1: [2],}")


def test_dict_tuple_one_nested():
    check_ast("{1: (2,)}")


def test_dict_tuple_one_nested_comma():
    check_ast("{1: (2,),}")


def test_dict_list_two_nested():
    check_ast("{1: [2], 3: [4]}")


def test_set_tuple_one_nested():
    check_ast("{(1,)}")


def test_set_tuple_two_nested():
    check_ast("{(1,), (2,)}")


def test_tuple_empty():
    check_ast("()")


def test_tuple_one_bare():
    check_ast("1,")


def test_tuple_two_bare():
    check_ast("1, 42")


def test_tuple_three_bare():
    check_ast("1, 42, 65")


def test_tuple_three_bare_comma():
    check_ast("1, 42, 65,")


def test_tuple_one_comma():
    check_ast("(1,)")


def test_tuple_two():
    check_ast("(1, 42)")


def test_tuple_three():
    check_ast("(1, 42, 65)")


def test_tuple_three_comma():
    check_ast("(1, 42, 65,)")


def test_bare_tuple_of_tuples():
    check_ast("(),")
    check_ast("((),),(1,)")
    check_ast("(),(),")
    check_ast("[],")
    check_ast("[],[]")
    check_ast("[],()")
    check_ast("(),[],")
    check_ast("((),[()],)")


def test_set_one():
    check_ast("{42}")


def test_set_one_comma():
    check_ast("{42,}")


def test_set_two():
    check_ast("{42, 65}")


def test_set_two_comma():
    check_ast("{42, 65,}")


def test_set_three():
    check_ast("{42, 65, 45}")


def test_dict_empty():
    check_ast("{}")


def test_dict_one():
    check_ast("{42: 65}")


def test_dict_one_comma():
    check_ast("{42: 65,}")


def test_dict_two():
    check_ast("{42: 65, 6: 28}")


def test_dict_two_comma():
    check_ast("{42: 65, 6: 28,}")


def test_dict_three():
    check_ast("{42: 65, 6: 28, 1: 2}")


@skip_if_py34
def test_dict_from_dict_two_xy():
    check_ast('{"x": 1, **{"y": 2}}')


@skip_if_py34
def test_dict_from_dict_two_x_first():
    check_ast('{"x": 1, **{"x": 2}}')


@skip_if_py34
def test_dict_from_dict_two_x_second():
    check_ast('{**{"x": 2}, "x": 1}')


@skip_if_py34
def test_unpack_range_tuple():
    check_stmts("*range(4),")


@skip_if_py34
def test_unpack_range_tuple_4():
    check_stmts("*range(4), 4")


@skip_if_py34
def test_unpack_range_tuple_parens():
    check_ast("(*range(4),)")


@skip_if_py34
def test_unpack_range_tuple_parens_4():
    check_ast("(*range(4), 4)")


@skip_if_py34
def test_unpack_range_list():
    check_ast("[*range(4)]")


@skip_if_py34
def test_unpack_range_list_4():
    check_ast("[*range(4), 4]")


@skip_if_py34
def test_unpack_range_set():
    check_ast("{*range(4)}")


@skip_if_py34
def test_unpack_range_set_4():
    check_ast("{*range(4), 4}")


def test_true():
    check_ast("True")


def test_false():
    check_ast("False")


def test_none():
    check_ast("None")


def test_elipssis():
    check_ast("...")


def test_not_implemented_name():
    check_ast("NotImplemented")


def test_genexpr():
    check_ast('(x for x in "mom")')


def test_genexpr_if():
    check_ast('(x for x in "mom" if True)')


def test_genexpr_if_and():
    check_ast('(x for x in "mom" if True and x == "m")')


def test_dbl_genexpr():
    check_ast('(x+y for x in "mom" for y in "dad")')


def test_genexpr_if_genexpr():
    check_ast('(x+y for x in "mom" if True for y in "dad")')


def test_genexpr_if_genexpr_if():
    check_ast('(x+y for x in "mom" if True for y in "dad" if y == "d")')


def test_listcomp():
    check_ast('[x for x in "mom"]')


def test_listcomp_if():
    check_ast('[x for x in "mom" if True]')


def test_listcomp_if_and():
    check_ast('[x for x in "mom" if True and x == "m"]')


def test_dbl_listcomp():
    check_ast('[x+y for x in "mom" for y in "dad"]')


def test_listcomp_if_listcomp():
    check_ast('[x+y for x in "mom" if True for y in "dad"]')


def test_listcomp_if_listcomp_if():
    check_ast('[x+y for x in "mom" if True for y in "dad" if y == "d"]')


def test_setcomp():
    check_ast('{x for x in "mom"}')


def test_setcomp_if():
    check_ast('{x for x in "mom" if True}')


def test_setcomp_if_and():
    check_ast('{x for x in "mom" if True and x == "m"}')


def test_dbl_setcomp():
    check_ast('{x+y for x in "mom" for y in "dad"}')


def test_setcomp_if_setcomp():
    check_ast('{x+y for x in "mom" if True for y in "dad"}')


def test_setcomp_if_setcomp_if():
    check_ast('{x+y for x in "mom" if True for y in "dad" if y == "d"}')


def test_dictcomp():
    check_ast('{x: x for x in "mom"}')


def test_dictcomp_unpack_parens():
    check_ast('{k: v for (k, v) in {"x": 42}.items()}')


def test_dictcomp_unpack_no_parens():
    check_ast('{k: v for k, v in {"x": 42}.items()}')


def test_dictcomp_if():
    check_ast('{x: x for x in "mom" if True}')


def test_dictcomp_if_and():
    check_ast('{x: x for x in "mom" if True and x == "m"}')


def test_dbl_dictcomp():
    check_ast('{x: y for x in "mom" for y in "dad"}')


def test_dictcomp_if_dictcomp():
    check_ast('{x: y for x in "mom" if True for y in "dad"}')


def test_dictcomp_if_dictcomp_if():
    check_ast('{x: y for x in "mom" if True for y in "dad" if y == "d"}')


def test_lambda():
    check_ast("lambda: 42")


def test_lambda_x():
    check_ast("lambda x: x")


def test_lambda_kwx():
    check_ast("lambda x=42: x")


def test_lambda_x_y():
    check_ast("lambda x, y: x")


def test_lambda_x_y_z():
    check_ast("lambda x, y, z: x")


def test_lambda_x_kwy():
    check_ast("lambda x, y=42: x")


def test_lambda_kwx_kwy():
    check_ast("lambda x=65, y=42: x")


def test_lambda_kwx_kwy_kwz():
    check_ast("lambda x=65, y=42, z=1: x")


def test_lambda_x_comma():
    check_ast("lambda x,: x")


def test_lambda_x_y_comma():
    check_ast("lambda x, y,: x")


def test_lambda_x_y_z_comma():
    check_ast("lambda x, y, z,: x")


def test_lambda_x_kwy_comma():
    check_ast("lambda x, y=42,: x")


def test_lambda_kwx_kwy_comma():
    check_ast("lambda x=65, y=42,: x")


def test_lambda_kwx_kwy_kwz_comma():
    check_ast("lambda x=65, y=42, z=1,: x")


def test_lambda_args():
    check_ast("lambda *args: 42")


def test_lambda_args_x():
    check_ast("lambda *args, x: 42")


def test_lambda_args_x_y():
    check_ast("lambda *args, x, y: 42")


def test_lambda_args_x_kwy():
    check_ast("lambda *args, x, y=10: 42")


def test_lambda_args_kwx_y():
    check_ast("lambda *args, x=10, y: 42")


def test_lambda_args_kwx_kwy():
    check_ast("lambda *args, x=42, y=65: 42")


def test_lambda_x_args():
    check_ast("lambda x, *args: 42")


def test_lambda_x_args_y():
    check_ast("lambda x, *args, y: 42")


def test_lambda_x_args_y_z():
    check_ast("lambda x, *args, y, z: 42")


def test_lambda_kwargs():
    check_ast("lambda **kwargs: 42")


def test_lambda_x_kwargs():
    check_ast("lambda x, **kwargs: 42")


def test_lambda_x_y_kwargs():
    check_ast("lambda x, y, **kwargs: 42")


def test_lambda_x_kwy_kwargs():
    check_ast("lambda x, y=42, **kwargs: 42")


def test_lambda_args_kwargs():
    check_ast("lambda *args, **kwargs: 42")


def test_lambda_x_args_kwargs():
    check_ast("lambda x, *args, **kwargs: 42")


def test_lambda_x_y_args_kwargs():
    check_ast("lambda x, y, *args, **kwargs: 42")


def test_lambda_kwx_args_kwargs():
    check_ast("lambda x=10, *args, **kwargs: 42")


def test_lambda_x_kwy_args_kwargs():
    check_ast("lambda x, y=42, *args, **kwargs: 42")


def test_lambda_x_args_y_kwargs():
    check_ast("lambda x, *args, y, **kwargs: 42")


def test_lambda_x_args_kwy_kwargs():
    check_ast("lambda x, *args, y=42, **kwargs: 42")


def test_lambda_args_y_kwargs():
    check_ast("lambda *args, y, **kwargs: 42")


def test_lambda_star_x():
    check_ast("lambda *, x: 42")


def test_lambda_star_x_y():
    check_ast("lambda *, x, y: 42")


def test_lambda_star_x_kwargs():
    check_ast("lambda *, x, **kwargs: 42")


def test_lambda_star_kwx_kwargs():
    check_ast("lambda *, x=42, **kwargs: 42")


def test_lambda_x_star_y():
    check_ast("lambda x, *, y: 42")


def test_lambda_x_y_star_z():
    check_ast("lambda x, y, *, z: 42")


def test_lambda_x_kwy_star_y():
    check_ast("lambda x, y=42, *, z: 42")


def test_lambda_x_kwy_star_kwy():
    check_ast("lambda x, y=42, *, z=65: 42")


def test_lambda_x_star_y_kwargs():
    check_ast("lambda x, *, y, **kwargs: 42")


def test_call_range():
    check_ast("range(6)")


def test_call_range_comma():
    check_ast("range(6,)")


def test_call_range_x_y():
    check_ast("range(6, 10)")


def test_call_range_x_y_comma():
    check_ast("range(6, 10,)")


def test_call_range_x_y_z():
    check_ast("range(6, 10, 2)")


def test_call_dict_kwx():
    check_ast("dict(start=10)")


def test_call_dict_kwx_comma():
    check_ast("dict(start=10,)")


def test_call_dict_kwx_kwy():
    check_ast("dict(start=10, stop=42)")


def test_call_tuple_gen():
    check_ast("tuple(x for x in [1, 2, 3])")


def test_call_tuple_genifs():
    check_ast("tuple(x for x in [1, 2, 3] if x < 3)")


def test_call_range_star():
    check_ast("range(*[1, 2, 3])")


def test_call_range_x_star():
    check_ast("range(1, *[2, 3])")


def test_call_int():
    check_ast('int(*["42"], base=8)')


def test_call_int_base_dict():
    check_ast('int(*["42"], **{"base": 8})')


def test_call_dict_kwargs():
    check_ast('dict(**{"base": 8})')


@skip_if_py34
def test_call_list_many_star_args():
    check_ast("min(*[1, 2], 3, *[4, 5])")


@skip_if_py34
def test_call_list_many_starstar_args():
    check_ast('dict(**{"a": 2}, v=3, **{"c": 5})')


@skip_if_py34
def test_call_list_many_star_and_starstar_args():
    check_ast('x(*[("a", 2)], *[("v", 3)], **{"c": 5})', False)


def test_call_alot():
    check_ast("x(1, *args, **kwargs)", False)


def test_call_alot_next():
    check_ast("x(x=1, *args, **kwargs)", False)


def test_call_alot_next_next():
    check_ast("x(x=1, *args, y=42, **kwargs)", False)


def test_getattr():
    check_ast("list.append")


def test_getattr_getattr():
    check_ast("list.append.__str__")


def test_dict_tuple_key():
    check_ast("{(42, 1): 65}")


def test_dict_tuple_key_get():
    check_ast("{(42, 1): 65}[42, 1]")


def test_dict_tuple_key_get_3():
    check_ast("{(42, 1, 3): 65}[42, 1, 3]")


def test_pipe_op():
    check_ast("{42} | {65}")


def test_pipe_op_two():
    check_ast("{42} | {65} | {1}")


def test_pipe_op_three():
    check_ast("{42} | {65} | {1} | {7}")


def test_xor_op():
    check_ast("{42} ^ {65}")


def test_xor_op_two():
    check_ast("{42} ^ {65} ^ {1}")


def test_xor_op_three():
    check_ast("{42} ^ {65} ^ {1} ^ {7}")


def test_xor_pipe():
    check_ast("{42} ^ {65} | {1}")


def test_amp_op():
    check_ast("{42} & {65}")


def test_amp_op_two():
    check_ast("{42} & {65} & {1}")


def test_amp_op_three():
    check_ast("{42} & {65} & {1} & {7}")


def test_lshift_op():
    check_ast("42 << 65")


def test_lshift_op_two():
    check_ast("42 << 65 << 1")


def test_lshift_op_three():
    check_ast("42 << 65 << 1 << 7")


def test_rshift_op():
    check_ast("42 >> 65")


def test_rshift_op_two():
    check_ast("42 >> 65 >> 1")


def test_rshift_op_three():
    check_ast("42 >> 65 >> 1 >> 7")


#
# statements
#


def test_equals():
    check_stmts("x = 42")


def test_equals_semi():
    check_stmts("x = 42;")


def test_x_y_equals_semi():
    check_stmts("x = y = 42")


def test_equals_two():
    check_stmts("x = 42; y = 65")


def test_equals_two_semi():
    check_stmts("x = 42; y = 65;")


def test_equals_three():
    check_stmts("x = 42; y = 65; z = 6")


def test_equals_three_semi():
    check_stmts("x = 42; y = 65; z = 6;")


def test_plus_eq():
    check_stmts("x = 42; x += 65")


def test_sub_eq():
    check_stmts("x = 42; x -= 2")


def test_times_eq():
    check_stmts("x = 42; x *= 2")


@skip_if_py34
def test_matmult_eq():
    check_stmts("x @= y", False)


def test_div_eq():
    check_stmts("x = 42; x /= 2")


def test_floordiv_eq():
    check_stmts("x = 42; x //= 2")


def test_pow_eq():
    check_stmts("x = 42; x **= 2")


def test_mod_eq():
    check_stmts("x = 42; x %= 2")


def test_xor_eq():
    check_stmts("x = 42; x ^= 2")


def test_ampersand_eq():
    check_stmts("x = 42; x &= 2")


def test_bitor_eq():
    check_stmts("x = 42; x |= 2")


def test_lshift_eq():
    check_stmts("x = 42; x <<= 2")


def test_rshift_eq():
    check_stmts("x = 42; x >>= 2")


def test_bare_unpack():
    check_stmts("x, y = 42, 65")


def test_lhand_group_unpack():
    check_stmts("(x, y) = 42, 65")


def test_rhand_group_unpack():
    check_stmts("x, y = (42, 65)")


def test_grouped_unpack():
    check_stmts("(x, y) = (42, 65)")


def test_double_grouped_unpack():
    check_stmts("(x, y) = (z, a) = (7, 8)")


def test_double_ungrouped_unpack():
    check_stmts("x, y = z, a = 7, 8")


def test_stary_eq():
    check_stmts("*y, = [1, 2, 3]")


def test_stary_x():
    check_stmts("*y, x = [1, 2, 3]")


def test_tuple_x_stary():
    check_stmts("(x, *y) = [1, 2, 3]")


def test_list_x_stary():
    check_stmts("[x, *y] = [1, 2, 3]")


def test_bare_x_stary():
    check_stmts("x, *y = [1, 2, 3]")


def test_bare_x_stary_z():
    check_stmts("x, *y, z = [1, 2, 2, 3]")


def test_equals_list():
    check_stmts("x = [42]; x[0] = 65")


def test_equals_dict():
    check_stmts("x = {42: 65}; x[42] = 3")


def test_equals_attr():
    check_stmts("class X(object):\n  pass\nx = X()\nx.a = 65")


@skip_if_lt_py36
def test_equals_annotation():
    check_stmts("x : int = 42")


def test_dict_keys():
    check_stmts('x = {"x": 1}\nx.keys()')


def test_assert_msg():
    check_stmts('assert True, "wow mom"')


def test_assert():
    check_stmts("assert True")


def test_pass():
    check_stmts("pass")


def test_del():
    check_stmts("x = 42; del x")


def test_del_comma():
    check_stmts("x = 42; del x,")


def test_del_two():
    check_stmts("x = 42; y = 65; del x, y")


def test_del_two_comma():
    check_stmts("x = 42; y = 65; del x, y,")


def test_del_with_parens():
    check_stmts("x = 42; y = 65; del (x, y)")


def test_raise():
    check_stmts("raise", False)


def test_raise_x():
    check_stmts("raise TypeError", False)


def test_raise_x_from():
    check_stmts("raise TypeError from x", False)


def test_import_x():
    check_stmts("import x", False)


def test_import_xy():
    check_stmts("import x.y", False)


def test_import_xyz():
    check_stmts("import x.y.z", False)


def test_from_x_import_y():
    check_stmts("from x import y", False)


def test_from_dot_import_y():
    check_stmts("from . import y", False)


def test_from_dotx_import_y():
    check_stmts("from .x import y", False)


def test_from_dotdotx_import_y():
    check_stmts("from ..x import y", False)


def test_from_dotdotdotx_import_y():
    check_stmts("from ...x import y", False)


def test_from_dotdotdotdotx_import_y():
    check_stmts("from ....x import y", False)


def test_from_import_x_y():
    check_stmts("import x, y", False)


def test_from_import_x_y_z():
    check_stmts("import x, y, z", False)


def test_from_dot_import_x_y():
    check_stmts("from . import x, y", False)


def test_from_dot_import_x_y_z():
    check_stmts("from . import x, y, z", False)


def test_from_dot_import_group_x_y():
    check_stmts("from . import (x, y)", False)


def test_import_x_as_y():
    check_stmts("import x as y", False)


def test_import_xy_as_z():
    check_stmts("import x.y as z", False)


def test_import_x_y_as_z():
    check_stmts("import x, y as z", False)


def test_import_x_as_y_z():
    check_stmts("import x as y, z", False)


def test_import_x_as_y_z_as_a():
    check_stmts("import x as y, z as a", False)


def test_from_dot_import_x_as_y():
    check_stmts("from . import x as y", False)


def test_from_x_import_star():
    check_stmts("from x import *", False)


def test_from_x_import_group_x_y_z():
    check_stmts("from x import (x, y, z)", False)


def test_from_x_import_group_x_y_z_comma():
    check_stmts("from x import (x, y, z,)", False)


def test_from_x_import_y_as_z():
    check_stmts("from x import y as z", False)


def test_from_x_import_y_as_z_a_as_b():
    check_stmts("from x import y as z, a as b", False)


def test_from_dotx_import_y_as_z_a_as_b_c_as_d():
    check_stmts("from .x import y as z, a as b, c as d", False)


def test_continue():
    check_stmts("continue", False)


def test_break():
    check_stmts("break", False)


def test_global():
    check_stmts("global x", False)


def test_global_xy():
    check_stmts("global x, y", False)


def test_nonlocal_x():
    check_stmts("nonlocal x", False)


def test_nonlocal_xy():
    check_stmts("nonlocal x, y", False)


def test_yield():
    check_stmts("yield", False)


def test_yield_x():
    check_stmts("yield x", False)


def test_yield_x_comma():
    check_stmts("yield x,", False)


def test_yield_x_y():
    check_stmts("yield x, y", False)


def test_yield_from_x():
    check_stmts("yield from x", False)


def test_return():
    check_stmts("return", False)


def test_return_x():
    check_stmts("return x", False)


def test_return_x_comma():
    check_stmts("return x,", False)


def test_return_x_y():
    check_stmts("return x, y", False)


def test_if_true():
    check_stmts("if True:\n  pass")


def test_if_true_twolines():
    check_stmts("if True:\n  pass\n  pass")


def test_if_true_twolines_deindent():
    check_stmts("if True:\n  pass\n  pass\npass")


def test_if_true_else():
    check_stmts("if True:\n  pass\nelse: \n  pass")


def test_if_true_x():
    check_stmts("if True:\n  x = 42")


def test_if_switch():
    check_stmts("x = 42\nif x == 1:\n  pass")


def test_if_switch_elif1_else():
    check_stmts("x = 42\nif x == 1:\n  pass\n" "elif x == 2:\n  pass\nelse:\n  pass")


def test_if_switch_elif2_else():
    check_stmts(
        "x = 42\nif x == 1:\n  pass\n"
        "elif x == 2:\n  pass\n"
        "elif x == 3:\n  pass\n"
        "elif x == 4:\n  pass\n"
        "else:\n  pass"
    )


def test_if_nested():
    check_stmts("x = 42\nif x == 1:\n  pass\n  if x == 4:\n     pass")


def test_while():
    check_stmts("while False:\n  pass")


def test_while_else():
    check_stmts("while False:\n  pass\nelse:\n  pass")


def test_for():
    check_stmts("for x in range(6):\n  pass")


def test_for_zip():
    check_stmts('for x, y in zip(range(6), "123456"):\n  pass')


def test_for_idx():
    check_stmts("x = [42]\nfor x[0] in range(3):\n  pass")


def test_for_zip_idx():
    check_stmts('x = [42]\nfor x[0], y in zip(range(6), "123456"):\n' "  pass")


def test_for_attr():
    check_stmts("for x.a in range(3):\n  pass", False)


def test_for_zip_attr():
    check_stmts('for x.a, y in zip(range(6), "123456"):\n  pass', False)


def test_for_else():
    check_stmts("for x in range(6):\n  pass\nelse:  pass")


@skip_if_py34
def test_async_for():
    check_stmts("async def f():\n    async for x in y:\n        pass\n", False)


def test_with():
    check_stmts("with x:\n  pass", False)


def test_with_as():
    check_stmts("with x as y:\n  pass", False)


def test_with_xy():
    check_stmts("with x, y:\n  pass", False)


def test_with_x_as_y_z():
    check_stmts("with x as y, z:\n  pass", False)


def test_with_x_as_y_a_as_b():
    check_stmts("with x as y, a as b:\n  pass", False)


def test_with_in_func():
    check_stmts("def f():\n    with x:\n        pass\n")


@skip_if_py34
def test_async_with():
    check_stmts("async def f():\n    async with x as y:\n        pass\n", False)


def test_try():
    check_stmts("try:\n  pass\nexcept:\n  pass", False)


def test_try_except_t():
    check_stmts("try:\n  pass\nexcept TypeError:\n  pass", False)


def test_try_except_t_as_e():
    check_stmts("try:\n  pass\nexcept TypeError as e:\n  pass", False)


def test_try_except_t_u():
    check_stmts("try:\n  pass\nexcept (TypeError, SyntaxError):\n  pass", False)


def test_try_except_t_u_as_e():
    check_stmts("try:\n  pass\nexcept (TypeError, SyntaxError) as e:\n  pass", False)


def test_try_except_t_except_u():
    check_stmts(
        "try:\n  pass\nexcept TypeError:\n  pass\n" "except SyntaxError as f:\n  pass",
        False,
    )


def test_try_except_else():
    check_stmts("try:\n  pass\nexcept:\n  pass\nelse:  pass", False)


def test_try_except_finally():
    check_stmts("try:\n  pass\nexcept:\n  pass\nfinally:  pass", False)


def test_try_except_else_finally():
    check_stmts(
        "try:\n  pass\nexcept:\n  pass\nelse:\n  pass" "\nfinally:  pass", False
    )


def test_try_finally():
    check_stmts("try:\n  pass\nfinally:  pass", False)


def test_func():
    check_stmts("def f():\n  pass")


def test_func_ret():
    check_stmts("def f():\n  return")


def test_func_ret_42():
    check_stmts("def f():\n  return 42")


def test_func_ret_42_65():
    check_stmts("def f():\n  return 42, 65")


def test_func_rarrow():
    check_stmts("def f() -> int:\n  pass")


def test_func_x():
    check_stmts("def f(x):\n  return x")


def test_func_kwx():
    check_stmts("def f(x=42):\n  return x")


def test_func_x_y():
    check_stmts("def f(x, y):\n  return x")


def test_func_x_y_z():
    check_stmts("def f(x, y, z):\n  return x")


def test_func_x_kwy():
    check_stmts("def f(x, y=42):\n  return x")


def test_func_kwx_kwy():
    check_stmts("def f(x=65, y=42):\n  return x")


def test_func_kwx_kwy_kwz():
    check_stmts("def f(x=65, y=42, z=1):\n  return x")


def test_func_x_comma():
    check_stmts("def f(x,):\n  return x")


def test_func_x_y_comma():
    check_stmts("def f(x, y,):\n  return x")


def test_func_x_y_z_comma():
    check_stmts("def f(x, y, z,):\n  return x")


def test_func_x_kwy_comma():
    check_stmts("def f(x, y=42,):\n  return x")


def test_func_kwx_kwy_comma():
    check_stmts("def f(x=65, y=42,):\n  return x")


def test_func_kwx_kwy_kwz_comma():
    check_stmts("def f(x=65, y=42, z=1,):\n  return x")


def test_func_args():
    check_stmts("def f(*args):\n  return 42")


def test_func_args_x():
    check_stmts("def f(*args, x):\n  return 42")


def test_func_args_x_y():
    check_stmts("def f(*args, x, y):\n  return 42")


def test_func_args_x_kwy():
    check_stmts("def f(*args, x, y=10):\n  return 42")


def test_func_args_kwx_y():
    check_stmts("def f(*args, x=10, y):\n  return 42")


def test_func_args_kwx_kwy():
    check_stmts("def f(*args, x=42, y=65):\n  return 42")


def test_func_x_args():
    check_stmts("def f(x, *args):\n  return 42")


def test_func_x_args_y():
    check_stmts("def f(x, *args, y):\n  return 42")


def test_func_x_args_y_z():
    check_stmts("def f(x, *args, y, z):\n  return 42")


def test_func_kwargs():
    check_stmts("def f(**kwargs):\n  return 42")


def test_func_x_kwargs():
    check_stmts("def f(x, **kwargs):\n  return 42")


def test_func_x_y_kwargs():
    check_stmts("def f(x, y, **kwargs):\n  return 42")


def test_func_x_kwy_kwargs():
    check_stmts("def f(x, y=42, **kwargs):\n  return 42")


def test_func_args_kwargs():
    check_stmts("def f(*args, **kwargs):\n  return 42")


def test_func_x_args_kwargs():
    check_stmts("def f(x, *args, **kwargs):\n  return 42")


def test_func_x_y_args_kwargs():
    check_stmts("def f(x, y, *args, **kwargs):\n  return 42")


def test_func_kwx_args_kwargs():
    check_stmts("def f(x=10, *args, **kwargs):\n  return 42")


def test_func_x_kwy_args_kwargs():
    check_stmts("def f(x, y=42, *args, **kwargs):\n  return 42")


def test_func_x_args_y_kwargs():
    check_stmts("def f(x, *args, y, **kwargs):\n  return 42")


def test_func_x_args_kwy_kwargs():
    check_stmts("def f(x, *args, y=42, **kwargs):\n  return 42")


def test_func_args_y_kwargs():
    check_stmts("def f(*args, y, **kwargs):\n  return 42")


def test_func_star_x():
    check_stmts("def f(*, x):\n  return 42")


def test_func_star_x_y():
    check_stmts("def f(*, x, y):\n  return 42")


def test_func_star_x_kwargs():
    check_stmts("def f(*, x, **kwargs):\n  return 42")


def test_func_star_kwx_kwargs():
    check_stmts("def f(*, x=42, **kwargs):\n  return 42")


def test_func_x_star_y():
    check_stmts("def f(x, *, y):\n  return 42")


def test_func_x_y_star_z():
    check_stmts("def f(x, y, *, z):\n  return 42")


def test_func_x_kwy_star_y():
    check_stmts("def f(x, y=42, *, z):\n  return 42")


def test_func_x_kwy_star_kwy():
    check_stmts("def f(x, y=42, *, z=65):\n  return 42")


def test_func_x_star_y_kwargs():
    check_stmts("def f(x, *, y, **kwargs):\n  return 42")


def test_func_tx():
    check_stmts("def f(x:int):\n  return x")


def test_func_txy():
    check_stmts("def f(x:int, y:float=10.0):\n  return x")


def test_class():
    check_stmts("class X:\n  pass")


def test_class_obj():
    check_stmts("class X(object):\n  pass")


def test_class_int_flt():
    check_stmts("class X(int, object):\n  pass")


def test_class_obj_kw():
    # technically valid syntax, though it will fail to compile
    check_stmts("class X(object=5):\n  pass", False)


def test_decorator():
    check_stmts("@g\ndef f():\n  pass", False)


def test_decorator_2():
    check_stmts("@h\n@g\ndef f():\n  pass", False)


def test_decorator_call():
    check_stmts("@g()\ndef f():\n  pass", False)


def test_decorator_call_args():
    check_stmts("@g(x, y=10)\ndef f():\n  pass", False)


def test_decorator_dot_call_args():
    check_stmts("@h.g(x, y=10)\ndef f():\n  pass", False)


def test_decorator_dot_dot_call_args():
    check_stmts("@i.h.g(x, y=10)\ndef f():\n  pass", False)


def test_broken_prompt_func():
    code = "def prompt():\n" "    return '{user}'.format(\n" "       user='me')\n"
    check_stmts(code, False)


def test_class_with_methods():
    code = (
        "class Test:\n"
        "   def __init__(self):\n"
        '       self.msg("hello world")\n'
        "   def msg(self, m):\n"
        "      print(m)\n"
    )
    check_stmts(code, False)


def test_nested_functions():
    code = (
        "def test(x):\n"
        "    def test2(y):\n"
        "        return y+x\n"
        "    return test2\n"
    )
    check_stmts(code, False)


def test_function_blank_line():
    code = (
        "def foo():\n"
        "    ascii_art = [\n"
        '        "(╯°□°）╯︵ ┻━┻",\n'
        r'        "¯\\_(ツ)_/¯",'
        "\n"
        r'        "┻━┻︵ \\(°□°)/ ︵ ┻━┻",'
        "\n"
        "    ]\n"
        "\n"
        "    import random\n"
        "    i = random.randint(0,len(ascii_art)) - 1\n"
        '    print("    Get to work!")\n'
        "    print(ascii_art[i])\n"
    )
    check_stmts(code, False)


@skip_if_py34
def test_async_func():
    check_stmts("async def f():\n  pass\n")


@skip_if_py34
def test_async_decorator():
    check_stmts("@g\nasync def f():\n  pass", False)


@skip_if_py34
def test_async_await():
    check_stmts("async def f():\n    await fut\n", False)


#
# Xonsh specific syntax
#


def test_path_literal():
    check_xonsh_ast({}, 'p"/foo"', False)
    check_xonsh_ast({}, 'pr"/foo"', False)
    check_xonsh_ast({}, 'rp"/foo"', False)
    check_xonsh_ast({}, 'pR"/foo"', False)
    check_xonsh_ast({}, 'Rp"/foo"', False)


def test_dollar_name():
    check_xonsh_ast({"WAKKA": 42}, "$WAKKA")


def test_dollar_py():
    check_xonsh({"WAKKA": 42}, 'x = "WAKKA"; y = ${x}')


def test_dollar_py_test():
    check_xonsh_ast({"WAKKA": 42}, '${None or "WAKKA"}')


def test_dollar_py_recursive_name():
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, "${$JAWAKA}")


def test_dollar_py_test_recursive_name():
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, "${None or $JAWAKA}")


def test_dollar_py_test_recursive_test():
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, '${${"JAWA" + $JAWAKA[-2:]}}')


def test_dollar_name_set():
    check_xonsh({"WAKKA": 42}, "$WAKKA = 42")


def test_dollar_py_set():
    check_xonsh({"WAKKA": 42}, 'x = "WAKKA"; ${x} = 65')


def test_dollar_sub():
    check_xonsh_ast({}, "$(ls)", False)


def test_dollar_sub_space():
    check_xonsh_ast({}, "$(ls )", False)


def test_ls_dot():
    check_xonsh_ast({}, "$(ls .)", False)


def test_lambda_in_atparens():
    check_xonsh_ast(
        {}, '$(echo hello | @(lambda a, s=None: "hey!") foo bar baz)', False
    )


def test_generator_in_atparens():
    check_xonsh_ast({}, "$(echo @(i**2 for i in range(20)))", False)


def test_bare_tuple_in_atparens():
    check_xonsh_ast({}, '$(echo @("a", 7))', False)


def test_nested_madness():
    check_xonsh_ast(
        {},
        "$(@$(which echo) ls | @(lambda a, s=None: $(@(s.strip()) @(a[1]))) foo -la baz)",
        False,
    )


def test_atparens_intoken():
    check_xonsh_ast({}, "![echo /x/@(y)/z]", False)


def test_ls_dot_nesting():
    check_xonsh_ast({}, '$(ls @(None or "."))', False)


def test_ls_dot_nesting_var():
    check_xonsh({}, 'x = "."; $(ls @(None or x))', False)


def test_ls_dot_str():
    check_xonsh_ast({}, '$(ls ".")', False)


def test_ls_nest_ls():
    check_xonsh_ast({}, "$(ls $(ls))", False)


def test_ls_nest_ls_dashl():
    check_xonsh_ast({}, "$(ls $(ls) -l)", False)


def test_ls_envvar_strval():
    check_xonsh_ast({"WAKKA": "."}, "$(ls $WAKKA)", False)


def test_ls_envvar_listval():
    check_xonsh_ast({"WAKKA": [".", "."]}, "$(ls $WAKKA)", False)


def test_bang_sub():
    check_xonsh_ast({}, "!(ls)", False)


def test_bang_sub_space():
    check_xonsh_ast({}, "!(ls )", False)


def test_bang_ls_dot():
    check_xonsh_ast({}, "!(ls .)", False)


def test_bang_ls_dot_nesting():
    check_xonsh_ast({}, '!(ls @(None or "."))', False)


def test_bang_ls_dot_nesting_var():
    check_xonsh({}, 'x = "."; !(ls @(None or x))', False)


def test_bang_ls_dot_str():
    check_xonsh_ast({}, '!(ls ".")', False)


def test_bang_ls_nest_ls():
    check_xonsh_ast({}, "!(ls $(ls))", False)


def test_bang_ls_nest_ls_dashl():
    check_xonsh_ast({}, "!(ls $(ls) -l)", False)


def test_bang_ls_envvar_strval():
    check_xonsh_ast({"WAKKA": "."}, "!(ls $WAKKA)", False)


def test_bang_ls_envvar_listval():
    check_xonsh_ast({"WAKKA": [".", "."]}, "!(ls $WAKKA)", False)


def test_question():
    check_xonsh_ast({}, "range?")


def test_dobquestion():
    check_xonsh_ast({}, "range??")


def test_question_chain():
    check_xonsh_ast({}, "range?.index?")


def test_ls_regex():
    check_xonsh_ast({}, "$(ls `[Ff]+i*LE` -l)", False)


def test_backtick():
    check_xonsh_ast({}, "print(`.*`)", False)


def test_ls_regex_octothorpe():
    check_xonsh_ast({}, "$(ls `#[Ff]+i*LE` -l)", False)


def test_ls_explicitregex():
    check_xonsh_ast({}, "$(ls r`[Ff]+i*LE` -l)", False)


def test_rbacktick():
    check_xonsh_ast({}, "print(r`.*`)", False)


def test_ls_explicitregex_octothorpe():
    check_xonsh_ast({}, "$(ls r`#[Ff]+i*LE` -l)", False)


def test_ls_glob():
    check_xonsh_ast({}, "$(ls g`[Ff]+i*LE` -l)", False)


def test_gbacktick():
    check_xonsh_ast({}, "print(g`.*`)", False)


def test_pbacktrick():
    check_xonsh_ast({}, "print(p`.*`)", False)


def test_pgbacktick():
    check_xonsh_ast({}, "print(pg`.*`)", False)


def test_prbacktick():
    check_xonsh_ast({}, "print(pr`.*`)", False)


def test_ls_glob_octothorpe():
    check_xonsh_ast({}, "$(ls g`#[Ff]+i*LE` -l)", False)


def test_ls_customsearch():
    check_xonsh_ast({}, "$(ls @foo`[Ff]+i*LE` -l)", False)


def test_custombacktick():
    check_xonsh_ast({}, "print(@foo`.*`)", False)


def test_ls_customsearch_octothorpe():
    check_xonsh_ast({}, "$(ls @foo`#[Ff]+i*LE` -l)", False)


def test_injection():
    check_xonsh_ast({}, "$[@$(which python)]", False)


def test_rhs_nested_injection():
    check_xonsh_ast({}, "$[ls @$(dirname @$(which python))]", False)


def test_backtick_octothorpe():
    check_xonsh_ast({}, "print(`#.*`)", False)


def test_uncaptured_sub():
    check_xonsh_ast({}, "$[ls]", False)


def test_hiddenobj_sub():
    check_xonsh_ast({}, "![ls]", False)


def test_slash_envarv_echo():
    check_xonsh_ast({}, "![echo $HOME/place]", False)


def test_echo_double_eq():
    check_xonsh_ast({}, "![echo yo==yo]", False)


def test_bang_two_cmds_one_pipe():
    check_xonsh_ast({}, "!(ls | grep wakka)", False)


def test_bang_three_cmds_two_pipes():
    check_xonsh_ast({}, "!(ls | grep wakka | grep jawaka)", False)


def test_bang_one_cmd_write():
    check_xonsh_ast({}, "!(ls > x.py)", False)


def test_bang_one_cmd_append():
    check_xonsh_ast({}, "!(ls >> x.py)", False)


def test_bang_two_cmds_write():
    check_xonsh_ast({}, "!(ls | grep wakka > x.py)", False)


def test_bang_two_cmds_append():
    check_xonsh_ast({}, "!(ls | grep wakka >> x.py)", False)


def test_bang_cmd_background():
    check_xonsh_ast({}, "!(emacs ugggh &)", False)


def test_bang_cmd_background_nospace():
    check_xonsh_ast({}, "!(emacs ugggh&)", False)


def test_bang_git_quotes_no_space():
    check_xonsh_ast({}, '![git commit -am "wakka"]', False)


def test_bang_git_quotes_space():
    check_xonsh_ast({}, '![git commit -am "wakka jawaka"]', False)


def test_bang_git_two_quotes_space():
    check_xonsh(
        {},
        '![git commit -am "wakka jawaka"]\n' '![git commit -am "flock jawaka"]\n',
        False,
    )


def test_bang_git_two_quotes_space_space():
    check_xonsh(
        {},
        '![git commit -am "wakka jawaka" ]\n'
        '![git commit -am "flock jawaka milwaka" ]\n',
        False,
    )


def test_bang_ls_quotes_3_space():
    check_xonsh_ast({}, '![ls "wakka jawaka baraka"]', False)


def test_two_cmds_one_pipe():
    check_xonsh_ast({}, "$(ls | grep wakka)", False)


def test_three_cmds_two_pipes():
    check_xonsh_ast({}, "$(ls | grep wakka | grep jawaka)", False)


def test_two_cmds_one_and_brackets():
    check_xonsh_ast({}, "![ls me] and ![grep wakka]", False)


def test_three_cmds_two_ands():
    check_xonsh_ast({}, "![ls] and ![grep wakka] and ![grep jawaka]", False)


def test_two_cmds_one_doubleamps():
    check_xonsh_ast({}, "![ls] && ![grep wakka]", False)


def test_three_cmds_two_doubleamps():
    check_xonsh_ast({}, "![ls] && ![grep wakka] && ![grep jawaka]", False)


def test_two_cmds_one_or():
    check_xonsh_ast({}, "![ls] or ![grep wakka]", False)


def test_three_cmds_two_ors():
    check_xonsh_ast({}, "![ls] or ![grep wakka] or ![grep jawaka]", False)


def test_two_cmds_one_doublepipe():
    check_xonsh_ast({}, "![ls] || ![grep wakka]", False)


def test_three_cmds_two_doublepipe():
    check_xonsh_ast({}, "![ls] || ![grep wakka] || ![grep jawaka]", False)


def test_one_cmd_write():
    check_xonsh_ast({}, "$(ls > x.py)", False)


def test_one_cmd_append():
    check_xonsh_ast({}, "$(ls >> x.py)", False)


def test_two_cmds_write():
    check_xonsh_ast({}, "$(ls | grep wakka > x.py)", False)


def test_two_cmds_append():
    check_xonsh_ast({}, "$(ls | grep wakka >> x.py)", False)


def test_cmd_background():
    check_xonsh_ast({}, "$(emacs ugggh &)", False)


def test_cmd_background_nospace():
    check_xonsh_ast({}, "$(emacs ugggh&)", False)


def test_git_quotes_no_space():
    check_xonsh_ast({}, '$[git commit -am "wakka"]', False)


def test_git_quotes_space():
    check_xonsh_ast({}, '$[git commit -am "wakka jawaka"]', False)


def test_git_two_quotes_space():
    check_xonsh(
        {},
        '$[git commit -am "wakka jawaka"]\n' '$[git commit -am "flock jawaka"]\n',
        False,
    )


def test_git_two_quotes_space_space():
    check_xonsh(
        {},
        '$[git commit -am "wakka jawaka" ]\n'
        '$[git commit -am "flock jawaka milwaka" ]\n',
        False,
    )


def test_ls_quotes_3_space():
    check_xonsh_ast({}, '$[ls "wakka jawaka baraka"]', False)


def test_echo_comma():
    check_xonsh_ast({}, "![echo ,]", False)


def test_echo_internal_comma():
    check_xonsh_ast({}, "![echo 1,2]", False)


def test_comment_only():
    check_xonsh_ast({}, "# hello")


def test_echo_slash_question():
    check_xonsh_ast({}, "![echo /?]", False)


def test_bad_quotes():
    with pytest.raises(SyntaxError):
        check_xonsh_ast({}, '![echo """hello]', False)


def test_redirect():
    assert check_xonsh_ast({}, "$[cat < input.txt]", False)
    assert check_xonsh_ast({}, "$[< input.txt cat]", False)


@pytest.mark.parametrize(
    "case",
    [
        "![(cat)]",
        "![(cat;)]",
        "![(cd path; ls; cd)]",
        '![(echo "abc"; sleep 1; echo "def")]',
        '![(echo "abc"; sleep 1; echo "def") | grep abc]',
        "![(if True:\n   ls\nelse:\n   echo not true)]",
    ],
)
def test_use_subshell(case):
    check_xonsh_ast({}, case, False, debug_level=0)


@pytest.mark.parametrize(
    "case",
    [
        "$[cat < /path/to/input.txt]",
        "$[(cat) < /path/to/input.txt]",
        "$[< /path/to/input.txt cat]",
        "![< /path/to/input.txt]",
        "![< /path/to/input.txt > /path/to/output.txt]",
    ],
)
def test_redirect_abspath(case):
    assert check_xonsh_ast({}, case, False)


@pytest.mark.parametrize("case", ["", "o", "out", "1"])
def test_redirect_output(case):
    assert check_xonsh_ast({}, '$[echo "test" {}> test.txt]'.format(case), False)
    assert check_xonsh_ast(
        {}, '$[< input.txt echo "test" {}> test.txt]'.format(case), False
    )
    assert check_xonsh_ast(
        {}, '$[echo "test" {}> test.txt < input.txt]'.format(case), False
    )


@pytest.mark.parametrize("case", ["e", "err", "2"])
def test_redirect_error(case):
    assert check_xonsh_ast({}, '$[echo "test" {}> test.txt]'.format(case), False)
    assert check_xonsh_ast(
        {}, '$[< input.txt echo "test" {}> test.txt]'.format(case), False
    )
    assert check_xonsh_ast(
        {}, '$[echo "test" {}> test.txt < input.txt]'.format(case), False
    )


@pytest.mark.parametrize("case", ["a", "all", "&"])
def test_redirect_all(case):
    assert check_xonsh_ast({}, '$[echo "test" {}> test.txt]'.format(case), False)
    assert check_xonsh_ast(
        {}, '$[< input.txt echo "test" {}> test.txt]'.format(case), False
    )
    assert check_xonsh_ast(
        {}, '$[echo "test" {}> test.txt < input.txt]'.format(case), False
    )


@pytest.mark.parametrize(
    "r",
    [
        "e>o",
        "e>out",
        "err>o",
        "2>1",
        "e>1",
        "err>1",
        "2>out",
        "2>o",
        "err>&1",
        "e>&1",
        "2>&1",
    ],
)
@pytest.mark.parametrize("o", ["", "o", "out", "1"])
def test_redirect_error_to_output(r, o):
    assert check_xonsh_ast({}, '$[echo "test" {} {}> test.txt]'.format(r, o), False)
    assert check_xonsh_ast(
        {}, '$[< input.txt echo "test" {} {}> test.txt]'.format(r, o), False
    )
    assert check_xonsh_ast(
        {}, '$[echo "test" {} {}> test.txt < input.txt]'.format(r, o), False
    )


@pytest.mark.parametrize(
    "r",
    [
        "o>e",
        "o>err",
        "out>e",
        "1>2",
        "o>2",
        "out>2",
        "1>err",
        "1>e",
        "out>&2",
        "o>&2",
        "1>&2",
    ],
)
@pytest.mark.parametrize("e", ["e", "err", "2"])
def test_redirect_output_to_error(r, e):
    assert check_xonsh_ast({}, '$[echo "test" {} {}> test.txt]'.format(r, e), False)
    assert check_xonsh_ast(
        {}, '$[< input.txt echo "test" {} {}> test.txt]'.format(r, e), False
    )
    assert check_xonsh_ast(
        {}, '$[echo "test" {} {}> test.txt < input.txt]'.format(r, e), False
    )


def test_macro_call_empty():
    assert check_xonsh_ast({}, "f!()", False)


MACRO_ARGS = [
    "x",
    "True",
    "None",
    "import os",
    "x=10",
    '"oh no, mom"',
    "...",
    " ... ",
    "if True:\n  pass",
    "{x: y}",
    "{x: y, 42: 5}",
    "{1, 2, 3,}",
    "(x,y)",
    "(x, y)",
    "((x, y), z)",
    "g()",
    "range(10)",
    "range(1, 10, 2)",
    "()",
    "{}",
    "[]",
    "[1, 2]",
    "@(x)",
    "!(ls -l)",
    "![ls -l]",
    "$(ls -l)",
    "${x + y}",
    "$[ls -l]",
    "@$(which xonsh)",
]


@pytest.mark.parametrize("s", MACRO_ARGS)
def test_macro_call_one_arg(s):
    f = "f!({})".format(s)
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


@pytest.mark.parametrize("s,t", itertools.product(MACRO_ARGS[::2], MACRO_ARGS[1::2]))
def test_macro_call_two_args(s, t):
    f = "f!({}, {})".format(s, t)
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 2
    assert args[0].s == s.strip()
    assert args[1].s == t.strip()


@pytest.mark.parametrize(
    "s,t,u", itertools.product(MACRO_ARGS[::3], MACRO_ARGS[1::3], MACRO_ARGS[2::3])
)
def test_macro_call_three_args(s, t, u):
    f = "f!({}, {}, {})".format(s, t, u)
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 3
    assert args[0].s == s.strip()
    assert args[1].s == t.strip()
    assert args[2].s == u.strip()


@pytest.mark.parametrize("s", MACRO_ARGS)
def test_macro_call_one_trailing(s):
    f = "f!({0},)".format(s)
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


@pytest.mark.parametrize("s", MACRO_ARGS)
def test_macro_call_one_trailing_space(s):
    f = "f!( {0}, )".format(s)
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


SUBPROC_MACRO_OC = [("!(", ")"), ("$(", ")"), ("![", "]"), ("$[", "]")]


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize("body", ["echo!", "echo !", "echo ! "])
def test_empty_subprocbang(opener, closer, body):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 2
    assert cmd[1].s == ""


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize("body", ["echo!x", "echo !x", "echo !x", "echo ! x"])
def test_single_subprocbang(opener, closer, body):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 2
    assert cmd[1].s == "x"


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize(
    "body", ["echo -n!x", "echo -n!x", "echo -n !x", "echo -n ! x"]
)
def test_arg_single_subprocbang(opener, closer, body):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 3
    assert cmd[2].s == "x"


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize("ipener, iloser", [("$(", ")"), ("@$(", ")"), ("$[", "]")])
@pytest.mark.parametrize(
    "body", ["echo -n!x", "echo -n!x", "echo -n !x", "echo -n ! x"]
)
def test_arg_single_subprocbang_nested(opener, closer, ipener, iloser, body):
    code = opener + "echo " + ipener + body + iloser + closer
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 3
    assert cmd[2].s == "x"


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize(
    "body",
    [
        "echo!x + y",
        "echo !x + y",
        "echo !x + y",
        "echo ! x + y",
        "timeit! bang! and more",
        "timeit! recurse() and more",
        "timeit! recurse[] and more",
        "timeit! recurse!() and more",
        "timeit! recurse![] and more",
        "timeit! recurse$() and more",
        "timeit! recurse$[] and more",
        "timeit! recurse!() and more",
        "timeit!!!!",
        "timeit! (!)",
        "timeit! [!]",
        "timeit!!(ls)",
        'timeit!"!)"',
    ],
)
def test_many_subprocbang(opener, closer, body):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 2
    assert cmd[1].s == body.partition("!")[-1].strip()


WITH_BANG_RAWSUITES = [
    "pass\n",
    "x = 42\ny = 12\n",
    'export PATH="yo:momma"\necho $PATH\n',
    ("with q as t:\n" "    v = 10\n" "\n"),
    (
        "with q as t:\n"
        "    v = 10\n"
        "\n"
        "for x in range(6):\n"
        "    if True:\n"
        "        pass\n"
        "    else:\n"
        "        ls -l\n"
        "\n"
        "a = 42\n"
    ),
]


@pytest.mark.parametrize("body", WITH_BANG_RAWSUITES)
def test_withbang_single_suite(body):
    code = "with! x:\n{}".format(textwrap.indent(body, "    "))
    tree = check_xonsh_ast({}, code, False, return_obs=True, mode="exec")
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 1
    item = wither.items[0]
    s = item.context_expr.args[1].s
    assert s == body


@pytest.mark.parametrize("body", WITH_BANG_RAWSUITES)
def test_withbang_as_single_suite(body):
    code = "with! x as y:\n{}".format(textwrap.indent(body, "    "))
    tree = check_xonsh_ast({}, code, False, return_obs=True, mode="exec")
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 1
    item = wither.items[0]
    assert item.optional_vars.id == "y"
    s = item.context_expr.args[1].s
    assert s == body


@pytest.mark.parametrize("body", WITH_BANG_RAWSUITES)
def test_withbang_single_suite_trailing(body):
    code = "with! x:\n{}\nprint(x)\n".format(textwrap.indent(body, "    "))
    tree = check_xonsh_ast(
        {},
        code,
        False,
        return_obs=True,
        mode="exec",
        # debug_level=100
    )
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 1
    item = wither.items[0]
    s = item.context_expr.args[1].s
    assert s == body + "\n"


WITH_BANG_RAWSIMPLE = [
    "pass",
    "x = 42; y = 12",
    'export PATH="yo:momma"; echo $PATH',
    "[1,\n    2,\n    3]",
]


@pytest.mark.parametrize("body", WITH_BANG_RAWSIMPLE)
def test_withbang_single_simple(body):
    code = "with! x: {}\n".format(body)
    tree = check_xonsh_ast({}, code, False, return_obs=True, mode="exec")
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 1
    item = wither.items[0]
    s = item.context_expr.args[1].s
    assert s == body


@pytest.mark.parametrize("body", WITH_BANG_RAWSIMPLE)
def test_withbang_single_simple_opt(body):
    code = "with! x as y: {}\n".format(body)
    tree = check_xonsh_ast({}, code, False, return_obs=True, mode="exec")
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 1
    item = wither.items[0]
    assert item.optional_vars.id == "y"
    s = item.context_expr.args[1].s
    assert s == body


@pytest.mark.parametrize("body", WITH_BANG_RAWSUITES)
def test_withbang_as_many_suite(body):
    code = "with! x as a, y as b, z as c:\n{}"
    code = code.format(textwrap.indent(body, "    "))
    tree = check_xonsh_ast({}, code, False, return_obs=True, mode="exec")
    assert isinstance(tree, AST)
    wither = tree.body[0]
    assert isinstance(wither, With)
    assert len(wither.body) == 1
    assert isinstance(wither.body[0], Pass)
    assert len(wither.items) == 3
    for i, targ in enumerate("abc"):
        item = wither.items[i]
        assert item.optional_vars.id == targ
        s = item.context_expr.args[1].s
        assert s == body


# test invalid expressions


def test_syntax_error_del_literal():
    with pytest.raises(SyntaxError):
        PARSER.parse("del 7")


def test_syntax_error_del_constant():
    with pytest.raises(SyntaxError):
        PARSER.parse("del True")


def test_syntax_error_del_emptytuple():
    with pytest.raises(SyntaxError):
        PARSER.parse("del ()")


def test_syntax_error_del_call():
    with pytest.raises(SyntaxError):
        PARSER.parse("del foo()")


def test_syntax_error_del_lambda():
    with pytest.raises(SyntaxError):
        PARSER.parse('del lambda x: "yay"')


def test_syntax_error_del_ifexp():
    with pytest.raises(SyntaxError):
        PARSER.parse("del x if y else z")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_del_comps(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("del {}".format(exp))


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_del_ops(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("del {}".format(exp))


@pytest.mark.parametrize("exp", ["x > y", "x > y == z"])
def test_syntax_error_del_cmp(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("del {}".format(exp))


def test_syntax_error_lonely_del():
    with pytest.raises(SyntaxError):
        PARSER.parse("del")


def test_syntax_error_assign_literal():
    with pytest.raises(SyntaxError):
        PARSER.parse("7 = x")


def test_syntax_error_assign_constant():
    with pytest.raises(SyntaxError):
        PARSER.parse("True = 8")


def test_syntax_error_assign_emptytuple():
    with pytest.raises(SyntaxError):
        PARSER.parse("() = x")


def test_syntax_error_assign_call():
    with pytest.raises(SyntaxError):
        PARSER.parse("foo() = x")


def test_syntax_error_assign_lambda():
    with pytest.raises(SyntaxError):
        PARSER.parse('lambda x: "yay" = y')


def test_syntax_error_assign_ifexp():
    with pytest.raises(SyntaxError):
        PARSER.parse("x if y else z = 8")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_assign_comps(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} = z".format(exp))


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_assign_ops(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} = z".format(exp))


@pytest.mark.parametrize("exp", ["x > y", "x > y == z"])
def test_syntax_error_assign_cmp(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} = a".format(exp))


def test_syntax_error_augassign_literal():
    with pytest.raises(SyntaxError):
        PARSER.parse("7 += x")


def test_syntax_error_augassign_constant():
    with pytest.raises(SyntaxError):
        PARSER.parse("True += 8")


def test_syntax_error_augassign_emptytuple():
    with pytest.raises(SyntaxError):
        PARSER.parse("() += x")


def test_syntax_error_augassign_call():
    with pytest.raises(SyntaxError):
        PARSER.parse("foo() += x")


def test_syntax_error_augassign_lambda():
    with pytest.raises(SyntaxError):
        PARSER.parse('lambda x: "yay" += y')


def test_syntax_error_augassign_ifexp():
    with pytest.raises(SyntaxError):
        PARSER.parse("x if y else z += 8")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_augassign_comps(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} += z".format(exp))


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_augassign_ops(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} += z".format(exp))


@pytest.mark.parametrize("exp", ["x > y", "x > y +=+= z"])
def test_syntax_error_augassign_cmp(exp):
    with pytest.raises(SyntaxError):
        PARSER.parse("{} += a".format(exp))


def test_syntax_error_bar_kwonlyargs():
    with pytest.raises(SyntaxError):
        PARSER.parse("def spam(*):\n   pass\n", mode="exec")
