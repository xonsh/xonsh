"""Tests the xonsh parser."""
import ast
import itertools
import textwrap

import pytest

from xonsh.ast import AST, Call, Pass, Str, With
from xonsh.parser import Parser
from xonsh.parsers.fstring_adaptor import FStringAdaptor
from xonsh.pytest.tools import (
    VER_MAJOR_MINOR,
    nodes_equal,
    skip_if_pre_3_8,
    skip_if_pre_3_10,
)


@pytest.fixture
def xsh(xession, monkeypatch, parser):
    monkeypatch.setattr(xession.execer, "parser", parser)
    return xession


@pytest.fixture(scope="module")
def parser():
    return Parser(yacc_optimize=False, yacc_debug=True)


@pytest.fixture
def check_ast(parser, xsh):
    def factory(inp, run=True, mode="eval", debug_level=0):
        __tracebackhide__ = True
        # expect a Python AST
        exp = ast.parse(inp, mode=mode)
        # observe something from xonsh
        obs = parser.parse(inp, debug_level=debug_level)
        # Check that they are equal
        assert nodes_equal(exp, obs)
        # round trip by running xonsh AST via Python
        if run:
            exec(compile(obs, "<test-ast>", mode))

    return factory


@pytest.fixture
def check_stmts(check_ast):
    def factory(inp, run=True, mode="exec", debug_level=0):
        __tracebackhide__ = True
        if not inp.endswith("\n"):
            inp += "\n"
        check_ast(inp, run=run, mode=mode, debug_level=debug_level)

    return factory


@pytest.fixture
def check_xonsh_ast(xsh, parser):
    def factory(
        xenv,
        inp,
        run=True,
        mode="eval",
        debug_level=0,
        return_obs=False,
        globals=None,
        locals=None,
    ):
        xsh.env.update(xenv)
        obs = parser.parse(inp, debug_level=debug_level)
        if obs is None:
            return  # comment only
        bytecode = compile(obs, "<test-xonsh-ast>", mode)
        if run:
            exec(bytecode, globals, locals)
        return obs if return_obs else True

    return factory


@pytest.fixture
def check_xonsh(check_xonsh_ast):
    def factory(xenv, inp, run=True, mode="exec"):
        __tracebackhide__ = True
        if not inp.endswith("\n"):
            inp += "\n"
        check_xonsh_ast(xenv, inp, run=run, mode=mode)

    return factory


@pytest.fixture
def eval_code(parser, xsh):
    def factory(inp, mode="eval", **loc_vars):
        obs = parser.parse(inp, debug_level=1)
        bytecode = compile(obs, "<test-xonsh-ast>", mode)
        return eval(bytecode, loc_vars)

    return factory


#
# Tests
#

#
# expressions
#


def test_int_literal(check_ast):
    check_ast("42")


def test_int_literal_underscore(check_ast):
    check_ast("4_2")


def test_float_literal(check_ast):
    check_ast("42.0")


def test_float_literal_underscore(check_ast):
    check_ast("4_2.4_2")


def test_imag_literal(check_ast):
    check_ast("42j")


def test_float_imag_literal(check_ast):
    check_ast("42.0j")


def test_complex(check_ast):
    check_ast("42+84j")


def test_str_literal(check_ast):
    check_ast('"hello"')


def test_bytes_literal(check_ast):
    check_ast('b"hello"')
    check_ast('B"hello"')
    check_ast('b"hello" b"world"')


def test_raw_literal(check_ast):
    check_ast('r"hell\\o"')
    check_ast('R"hell\\o"')


def test_f_literal(check_ast):
    check_ast('f"wakka{yo}yakka{42}"', run=False)
    check_ast('F"{yo}"', run=False)


@pytest.mark.parametrize(
    "first_prefix, second_prefix",
    itertools.product(["", "f", "r", "fr"], repeat=2),
)
def test_string_literal_concat(first_prefix, second_prefix, check_ast):
    check_ast(
        first_prefix + r"'11{a}22\n'" + " " + second_prefix + r"'33{b}44\n'", run=False
    )


def test_f_env_var(check_xonsh_ast):
    check_xonsh_ast({}, 'f"{$HOME}"', run=False)
    check_xonsh_ast({}, "f'{$XONSH_DEBUG}'", run=False)
    check_xonsh_ast({}, 'F"{$PATH} and {$XONSH_DEBUG}"', run=False)


fstring_adaptor_parameters = [
    ('f"$HOME"', "$HOME"),
    ('f"{0} - {1}"', "0 - 1"),
    ('f"{$HOME}"', "/foo/bar"),
    ('f"{ $HOME }"', "/foo/bar"),
    ("f\"{'$HOME'}\"", "$HOME"),
    ('f"$HOME  = {$HOME}"', "$HOME  = /foo/bar"),
    ("f\"{${'HOME'}}\"", "/foo/bar"),
    ("f'{${$FOO+$BAR}}'", "/foo/bar"),
    ("f\"${$FOO}{$BAR}={f'{$HOME}'}\"", "$HOME=/foo/bar"),
    (
        '''f"""foo
{f"_{$HOME}_"}
bar"""''',
        "foo\n_/foo/bar_\nbar",
    ),
    (
        '''f"""foo
{f"_{${'HOME'}}_"}
bar"""''',
        "foo\n_/foo/bar_\nbar",
    ),
    (
        '''f"""foo
{f"_{${ $FOO + $BAR }}_"}
bar"""''',
        "foo\n_/foo/bar_\nbar",
    ),
]
if VER_MAJOR_MINOR >= (3, 8):
    fstring_adaptor_parameters.append(("f'{$HOME=}'", "$HOME='/foo/bar'"))


@pytest.mark.parametrize("inp, exp", fstring_adaptor_parameters)
def test_fstring_adaptor(inp, exp, xsh, monkeypatch):
    joined_str_node = FStringAdaptor(inp, "f").run()
    assert isinstance(joined_str_node, ast.JoinedStr)
    node = ast.Expression(body=joined_str_node)
    code = compile(node, "<test_fstring_adaptor>", mode="eval")
    xenv = {"HOME": "/foo/bar", "FOO": "HO", "BAR": "ME"}
    for key, val in xenv.items():
        monkeypatch.setitem(xsh.env, key, val)
    obs = eval(code)
    assert exp == obs


def test_raw_bytes_literal(check_ast):
    check_ast('br"hell\\o"')
    check_ast('RB"hell\\o"')
    check_ast('Br"hell\\o"')
    check_ast('rB"hell\\o"')


def test_unary_plus(check_ast):
    check_ast("+1")


def test_unary_minus(check_ast):
    check_ast("-1")


def test_unary_invert(check_ast):
    check_ast("~1")


def test_binop_plus(check_ast):
    check_ast("42 + 65")


def test_binop_minus(check_ast):
    check_ast("42 - 65")


def test_binop_times(check_ast):
    check_ast("42 * 65")


def test_binop_matmult(check_ast):
    check_ast("x @ y", False)


def test_binop_div(check_ast):
    check_ast("42 / 65")


def test_binop_mod(check_ast):
    check_ast("42 % 65")


def test_binop_floordiv(check_ast):
    check_ast("42 // 65")


def test_binop_pow(check_ast):
    check_ast("2 ** 2")


def test_plus_pow(check_ast):
    check_ast("42 + 2 ** 2")


def test_plus_plus(check_ast):
    check_ast("42 + 65 + 6")


def test_plus_minus(check_ast):
    check_ast("42 + 65 - 6")


def test_minus_plus(check_ast):
    check_ast("42 - 65 + 6")


def test_minus_minus(check_ast):
    check_ast("42 - 65 - 6")


def test_minus_plus_minus(check_ast):
    check_ast("42 - 65 + 6 - 28")


def test_times_plus(check_ast):
    check_ast("42 * 65 + 6")


def test_plus_times(check_ast):
    check_ast("42 + 65 * 6")


def test_times_times(check_ast):
    check_ast("42 * 65 * 6")


def test_times_div(check_ast):
    check_ast("42 * 65 / 6")


def test_times_div_mod(check_ast):
    check_ast("42 * 65 / 6 % 28")


def test_times_div_mod_floor(check_ast):
    check_ast("42 * 65 / 6 % 28 // 13")


def test_str_str(check_ast):
    check_ast("\"hello\" 'mom'")


def test_str_str_str(check_ast):
    check_ast('"hello" \'mom\'    "wow"')


def test_str_plus_str(check_ast):
    check_ast("\"hello\" + 'mom'")


def test_str_times_int(check_ast):
    check_ast('"hello" * 20')


def test_int_times_str(check_ast):
    check_ast('2*"hello"')


def test_group_plus_times(check_ast):
    check_ast("(42 + 65) * 20")


def test_plus_group_times(check_ast):
    check_ast("42 + (65 * 20)")


def test_group(check_ast):
    check_ast("(42)")


def test_lt(check_ast):
    check_ast("42 < 65")


def test_gt(check_ast):
    check_ast("42 > 65")


def test_eq(check_ast):
    check_ast("42 == 65")


def test_le(check_ast):
    check_ast("42 <= 65")


def test_ge(check_ast):
    check_ast("42 >= 65")


def test_ne(check_ast):
    check_ast("42 != 65")


def test_in(check_ast):
    check_ast('"4" in "65"')


def test_is(check_ast):
    check_ast("int is float")  # avoid PY3.8 SyntaxWarning "is" with a literal


def test_not_in(check_ast):
    check_ast('"4" not in "65"')


def test_is_not(check_ast):
    check_ast("float is not int")


def test_lt_lt(check_ast):
    check_ast("42 < 65 < 105")


def test_lt_lt_lt(check_ast):
    check_ast("42 < 65 < 105 < 77")


def test_not(check_ast):
    check_ast("not 0")


def test_or(check_ast):
    check_ast("1 or 0")


def test_or_or(check_ast):
    check_ast("1 or 0 or 42")


def test_and(check_ast):
    check_ast("1 and 0")


def test_and_and(check_ast):
    check_ast("1 and 0 and 2")


def test_and_or(check_ast):
    check_ast("1 and 0 or 2")


def test_or_and(check_ast):
    check_ast("1 or 0 and 2")


def test_group_and_and(check_ast):
    check_ast("(1 and 0) and 2")


def test_group_and_or(check_ast):
    check_ast("(1 and 0) or 2")


def test_if_else_expr(check_ast):
    check_ast("42 if True else 65")


def test_if_else_expr_expr(check_ast):
    check_ast("42+5 if 1 == 2 else 65-5")


def test_subscription_syntaxes(eval_code):
    assert eval_code("[1, 2, 3][-1]") == 3
    assert eval_code("[1, 2, 3][-1]") == 3
    assert eval_code("'string'[-1]") == "g"


@pytest.fixture
def arr_container():
    # like numpy.r_
    class Arr:
        def __getitem__(self, item):
            return item

    return Arr()


def test_subscription_special_syntaxes(arr_container, eval_code):
    assert eval_code("arr[1, 2, 3]", arr=arr_container) == (1, 2, 3)
    # dataframe
    assert eval_code('arr[["a", "b"]]', arr=arr_container) == ["a", "b"]


# todo: enable this test
@pytest.mark.xfail
def test_subscription_special_syntaxes_2(arr_container, eval_code):
    # aliases
    d = {}
    eval_code("d[arr.__name__]=True", arr=arr_container, d=d)
    assert d == {"Arr": True}
    # extslice
    assert eval_code('arr[:, "2"]') == 2


def test_str_idx(check_ast):
    check_ast('"hello"[0]')


def test_str_slice(check_ast):
    check_ast('"hello"[0:3]')


def test_str_step(check_ast):
    check_ast('"hello"[0:3:1]')


def test_str_slice_all(check_ast):
    check_ast('"hello"[:]')


def test_str_slice_upper(check_ast):
    check_ast('"hello"[5:]')


def test_str_slice_lower(check_ast):
    check_ast('"hello"[:3]')


def test_str_slice_other(check_ast):
    check_ast('"hello"[::2]')


def test_str_slice_lower_other(check_ast):
    check_ast('"hello"[:3:2]')


def test_str_slice_upper_other(check_ast):
    check_ast('"hello"[3::2]')


def test_str_2slice(check_ast):
    check_ast('"hello"[0:3,0:3]', False)


def test_str_2step(check_ast):
    check_ast('"hello"[0:3:1,0:4:2]', False)


def test_str_2slice_all(check_ast):
    check_ast('"hello"[:,:]', False)


def test_str_2slice_upper(check_ast):
    check_ast('"hello"[5:,5:]', False)


def test_str_2slice_lower(check_ast):
    check_ast('"hello"[:3,:3]', False)


def test_str_2slice_lowerupper(check_ast):
    check_ast('"hello"[5:,:3]', False)


def test_str_2slice_other(check_ast):
    check_ast('"hello"[::2,::2]', False)


def test_str_2slice_lower_other(check_ast):
    check_ast('"hello"[:3:2,:3:2]', False)


def test_str_2slice_upper_other(check_ast):
    check_ast('"hello"[3::2,3::2]', False)


def test_str_3slice(check_ast):
    check_ast('"hello"[0:3,0:3,0:3]', False)


def test_str_3step(check_ast):
    check_ast('"hello"[0:3:1,0:4:2,1:3:2]', False)


def test_str_3slice_all(check_ast):
    check_ast('"hello"[:,:,:]', False)


def test_str_3slice_upper(check_ast):
    check_ast('"hello"[5:,5:,5:]', False)


def test_str_3slice_lower(check_ast):
    check_ast('"hello"[:3,:3,:3]', False)


def test_str_3slice_lowerlowerupper(check_ast):
    check_ast('"hello"[:3,:3,:3]', False)


def test_str_3slice_lowerupperlower(check_ast):
    check_ast('"hello"[:3,5:,:3]', False)


def test_str_3slice_lowerupperupper(check_ast):
    check_ast('"hello"[:3,5:,5:]', False)


def test_str_3slice_upperlowerlower(check_ast):
    check_ast('"hello"[5:,5:,:3]', False)


def test_str_3slice_upperlowerupper(check_ast):
    check_ast('"hello"[5:,:3,5:]', False)


def test_str_3slice_upperupperlower(check_ast):
    check_ast('"hello"[5:,5:,:3]', False)


def test_str_3slice_other(check_ast):
    check_ast('"hello"[::2,::2,::2]', False)


def test_str_3slice_lower_other(check_ast):
    check_ast('"hello"[:3:2,:3:2,:3:2]', False)


def test_str_3slice_upper_other(check_ast):
    check_ast('"hello"[3::2,3::2,3::2]', False)


def test_str_slice_true(check_ast):
    check_ast('"hello"[0:3,True]', False)


def test_str_true_slice(check_ast):
    check_ast('"hello"[True,0:3]', False)


def test_list_empty(check_ast):
    check_ast("[]")


def test_list_one(check_ast):
    check_ast("[1]")


def test_list_one_comma(check_ast):
    check_ast("[1,]")


def test_list_two(check_ast):
    check_ast("[1, 42]")


def test_list_three(check_ast):
    check_ast("[1, 42, 65]")


def test_list_three_comma(check_ast):
    check_ast("[1, 42, 65,]")


def test_list_one_nested(check_ast):
    check_ast("[[1]]")


def test_list_list_four_nested(check_ast):
    check_ast("[[1], [2], [3], [4]]")


def test_list_tuple_three_nested(check_ast):
    check_ast("[(1,), (2,), (3,)]")


def test_list_set_tuple_three_nested(check_ast):
    check_ast("[{(1,)}, {(2,)}, {(3,)}]")


def test_list_tuple_one_nested(check_ast):
    check_ast("[(1,)]")


def test_tuple_tuple_one_nested(check_ast):
    check_ast("((1,),)")


def test_dict_list_one_nested(check_ast):
    check_ast("{1: [2]}")


def test_dict_list_one_nested_comma(check_ast):
    check_ast("{1: [2],}")


def test_dict_tuple_one_nested(check_ast):
    check_ast("{1: (2,)}")


def test_dict_tuple_one_nested_comma(check_ast):
    check_ast("{1: (2,),}")


def test_dict_list_two_nested(check_ast):
    check_ast("{1: [2], 3: [4]}")


def test_set_tuple_one_nested(check_ast):
    check_ast("{(1,)}")


def test_set_tuple_two_nested(check_ast):
    check_ast("{(1,), (2,)}")


def test_tuple_empty(check_ast):
    check_ast("()")


def test_tuple_one_bare(check_ast):
    check_ast("1,")


def test_tuple_two_bare(check_ast):
    check_ast("1, 42")


def test_tuple_three_bare(check_ast):
    check_ast("1, 42, 65")


def test_tuple_three_bare_comma(check_ast):
    check_ast("1, 42, 65,")


def test_tuple_one_comma(check_ast):
    check_ast("(1,)")


def test_tuple_two(check_ast):
    check_ast("(1, 42)")


def test_tuple_three(check_ast):
    check_ast("(1, 42, 65)")


def test_tuple_three_comma(check_ast):
    check_ast("(1, 42, 65,)")


def test_bare_tuple_of_tuples(check_ast):
    check_ast("(),")
    check_ast("((),),(1,)")
    check_ast("(),(),")
    check_ast("[],")
    check_ast("[],[]")
    check_ast("[],()")
    check_ast("(),[],")
    check_ast("((),[()],)")


def test_set_one(check_ast):
    check_ast("{42}")


def test_set_one_comma(check_ast):
    check_ast("{42,}")


def test_set_two(check_ast):
    check_ast("{42, 65}")


def test_set_two_comma(check_ast):
    check_ast("{42, 65,}")


def test_set_three(check_ast):
    check_ast("{42, 65, 45}")


def test_dict_empty(check_ast):
    check_ast("{}")


def test_dict_one(check_ast):
    check_ast("{42: 65}")


def test_dict_one_comma(check_ast):
    check_ast("{42: 65,}")


def test_dict_two(check_ast):
    check_ast("{42: 65, 6: 28}")


def test_dict_two_comma(check_ast):
    check_ast("{42: 65, 6: 28,}")


def test_dict_three(check_ast):
    check_ast("{42: 65, 6: 28, 1: 2}")


def test_dict_from_dict_one(check_ast):
    check_ast('{**{"x": 2}}')


def test_dict_from_dict_one_comma(check_ast):
    check_ast('{**{"x": 2},}')


def test_dict_from_dict_two_xy(check_ast):
    check_ast('{"x": 1, **{"y": 2}}')


def test_dict_from_dict_two_x_first(check_ast):
    check_ast('{"x": 1, **{"x": 2}}')


def test_dict_from_dict_two_x_second(check_ast):
    check_ast('{**{"x": 2}, "x": 1}')


def test_dict_from_dict_two_x_none(check_ast):
    check_ast('{**{"x": 1}, **{"x": 2}}')


@pytest.mark.parametrize("third", [True, False])
@pytest.mark.parametrize("second", [True, False])
@pytest.mark.parametrize("first", [True, False])
def test_dict_from_dict_three_xyz(first, second, third, check_ast):
    val1 = '"x": 1' if first else '**{"x": 1}'
    val2 = '"y": 2' if second else '**{"y": 2}'
    val3 = '"z": 3' if third else '**{"z": 3}'
    check_ast("{" + val1 + "," + val2 + "," + val3 + "}")


def test_unpack_range_tuple(check_stmts):
    check_stmts("*range(4),")


def test_unpack_range_tuple_4(check_stmts):
    check_stmts("*range(4), 4")


def test_unpack_range_tuple_parens(check_ast):
    check_ast("(*range(4),)")


def test_unpack_range_tuple_parens_4(check_ast):
    check_ast("(*range(4), 4)")


def test_unpack_range_list(check_ast):
    check_ast("[*range(4)]")


def test_unpack_range_list_4(check_ast):
    check_ast("[*range(4), 4]")


def test_unpack_range_set(check_ast):
    check_ast("{*range(4)}")


def test_unpack_range_set_4(check_ast):
    check_ast("{*range(4), 4}")


def test_true(check_ast):
    check_ast("True")


def test_false(check_ast):
    check_ast("False")


def test_none(check_ast):
    check_ast("None")


def test_elipssis(check_ast):
    check_ast("...")


def test_not_implemented_name(check_ast):
    check_ast("NotImplemented")


def test_genexpr(check_ast):
    check_ast('(x for x in "mom")')


def test_genexpr_if(check_ast):
    check_ast('(x for x in "mom" if True)')


def test_genexpr_if_and(check_ast):
    check_ast('(x for x in "mom" if True and x == "m")')


def test_dbl_genexpr(check_ast):
    check_ast('(x+y for x in "mom" for y in "dad")')


def test_genexpr_if_genexpr(check_ast):
    check_ast('(x+y for x in "mom" if True for y in "dad")')


def test_genexpr_if_genexpr_if(check_ast):
    check_ast('(x+y for x in "mom" if True for y in "dad" if y == "d")')


def test_listcomp(check_ast):
    check_ast('[x for x in "mom"]')


def test_listcomp_if(check_ast):
    check_ast('[x for x in "mom" if True]')


def test_listcomp_if_and(check_ast):
    check_ast('[x for x in "mom" if True and x == "m"]')


def test_listcomp_multi_if(check_ast):
    check_ast('[x for x in "mom" if True if x in "mo" if x == "m"]')


def test_dbl_listcomp(check_ast):
    check_ast('[x+y for x in "mom" for y in "dad"]')


def test_listcomp_if_listcomp(check_ast):
    check_ast('[x+y for x in "mom" if True for y in "dad"]')


def test_listcomp_if_listcomp_if(check_ast):
    check_ast('[x+y for x in "mom" if True for y in "dad" if y == "d"]')


def test_setcomp(check_ast):
    check_ast('{x for x in "mom"}')


def test_setcomp_if(check_ast):
    check_ast('{x for x in "mom" if True}')


def test_setcomp_if_and(check_ast):
    check_ast('{x for x in "mom" if True and x == "m"}')


def test_dbl_setcomp(check_ast):
    check_ast('{x+y for x in "mom" for y in "dad"}')


def test_setcomp_if_setcomp(check_ast):
    check_ast('{x+y for x in "mom" if True for y in "dad"}')


def test_setcomp_if_setcomp_if(check_ast):
    check_ast('{x+y for x in "mom" if True for y in "dad" if y == "d"}')


def test_dictcomp(check_ast):
    check_ast('{x: x for x in "mom"}')


def test_dictcomp_unpack_parens(check_ast):
    check_ast('{k: v for (k, v) in {"x": 42}.items()}')


def test_dictcomp_unpack_no_parens(check_ast):
    check_ast('{k: v for k, v in {"x": 42}.items()}')


def test_dictcomp_if(check_ast):
    check_ast('{x: x for x in "mom" if True}')


def test_dictcomp_if_and(check_ast):
    check_ast('{x: x for x in "mom" if True and x == "m"}')


def test_dbl_dictcomp(check_ast):
    check_ast('{x: y for x in "mom" for y in "dad"}')


def test_dictcomp_if_dictcomp(check_ast):
    check_ast('{x: y for x in "mom" if True for y in "dad"}')


def test_dictcomp_if_dictcomp_if(check_ast):
    check_ast('{x: y for x in "mom" if True for y in "dad" if y == "d"}')


def test_lambda(check_ast):
    check_ast("lambda: 42")


def test_lambda_x(check_ast):
    check_ast("lambda x: x")


def test_lambda_kwx(check_ast):
    check_ast("lambda x=42: x")


def test_lambda_x_y(check_ast):
    check_ast("lambda x, y: x")


def test_lambda_x_y_z(check_ast):
    check_ast("lambda x, y, z: x")


def test_lambda_x_kwy(check_ast):
    check_ast("lambda x, y=42: x")


def test_lambda_kwx_kwy(check_ast):
    check_ast("lambda x=65, y=42: x")


def test_lambda_kwx_kwy_kwz(check_ast):
    check_ast("lambda x=65, y=42, z=1: x")


def test_lambda_x_comma(check_ast):
    check_ast("lambda x,: x")


def test_lambda_x_y_comma(check_ast):
    check_ast("lambda x, y,: x")


def test_lambda_x_y_z_comma(check_ast):
    check_ast("lambda x, y, z,: x")


def test_lambda_x_kwy_comma(check_ast):
    check_ast("lambda x, y=42,: x")


def test_lambda_kwx_kwy_comma(check_ast):
    check_ast("lambda x=65, y=42,: x")


def test_lambda_kwx_kwy_kwz_comma(check_ast):
    check_ast("lambda x=65, y=42, z=1,: x")


def test_lambda_args(check_ast):
    check_ast("lambda *args: 42")


def test_lambda_args_x(check_ast):
    check_ast("lambda *args, x: 42")


def test_lambda_args_x_y(check_ast):
    check_ast("lambda *args, x, y: 42")


def test_lambda_args_x_kwy(check_ast):
    check_ast("lambda *args, x, y=10: 42")


def test_lambda_args_kwx_y(check_ast):
    check_ast("lambda *args, x=10, y: 42")


def test_lambda_args_kwx_kwy(check_ast):
    check_ast("lambda *args, x=42, y=65: 42")


def test_lambda_x_args(check_ast):
    check_ast("lambda x, *args: 42")


def test_lambda_x_args_y(check_ast):
    check_ast("lambda x, *args, y: 42")


def test_lambda_x_args_y_z(check_ast):
    check_ast("lambda x, *args, y, z: 42")


def test_lambda_kwargs(check_ast):
    check_ast("lambda **kwargs: 42")


def test_lambda_x_kwargs(check_ast):
    check_ast("lambda x, **kwargs: 42")


def test_lambda_x_y_kwargs(check_ast):
    check_ast("lambda x, y, **kwargs: 42")


def test_lambda_x_kwy_kwargs(check_ast):
    check_ast("lambda x, y=42, **kwargs: 42")


def test_lambda_args_kwargs(check_ast):
    check_ast("lambda *args, **kwargs: 42")


def test_lambda_x_args_kwargs(check_ast):
    check_ast("lambda x, *args, **kwargs: 42")


def test_lambda_x_y_args_kwargs(check_ast):
    check_ast("lambda x, y, *args, **kwargs: 42")


def test_lambda_kwx_args_kwargs(check_ast):
    check_ast("lambda x=10, *args, **kwargs: 42")


def test_lambda_x_kwy_args_kwargs(check_ast):
    check_ast("lambda x, y=42, *args, **kwargs: 42")


def test_lambda_x_args_y_kwargs(check_ast):
    check_ast("lambda x, *args, y, **kwargs: 42")


def test_lambda_x_args_kwy_kwargs(check_ast):
    check_ast("lambda x, *args, y=42, **kwargs: 42")


def test_lambda_args_y_kwargs(check_ast):
    check_ast("lambda *args, y, **kwargs: 42")


def test_lambda_star_x(check_ast):
    check_ast("lambda *, x: 42")


def test_lambda_star_x_y(check_ast):
    check_ast("lambda *, x, y: 42")


def test_lambda_star_x_kwargs(check_ast):
    check_ast("lambda *, x, **kwargs: 42")


def test_lambda_star_kwx_kwargs(check_ast):
    check_ast("lambda *, x=42, **kwargs: 42")


def test_lambda_x_star_y(check_ast):
    check_ast("lambda x, *, y: 42")


def test_lambda_x_y_star_z(check_ast):
    check_ast("lambda x, y, *, z: 42")


def test_lambda_x_kwy_star_y(check_ast):
    check_ast("lambda x, y=42, *, z: 42")


def test_lambda_x_kwy_star_kwy(check_ast):
    check_ast("lambda x, y=42, *, z=65: 42")


def test_lambda_x_star_y_kwargs(check_ast):
    check_ast("lambda x, *, y, **kwargs: 42")


@skip_if_pre_3_8
def test_lambda_x_divide_y_star_z_kwargs(check_ast):
    check_ast("lambda x, /, y, *, z, **kwargs: 42")


def test_call_range(check_ast):
    check_ast("range(6)")


def test_call_range_comma(check_ast):
    check_ast("range(6,)")


def test_call_range_x_y(check_ast):
    check_ast("range(6, 10)")


def test_call_range_x_y_comma(check_ast):
    check_ast("range(6, 10,)")


def test_call_range_x_y_z(check_ast):
    check_ast("range(6, 10, 2)")


def test_call_dict_kwx(check_ast):
    check_ast("dict(start=10)")


def test_call_dict_kwx_comma(check_ast):
    check_ast("dict(start=10,)")


def test_call_dict_kwx_kwy(check_ast):
    check_ast("dict(start=10, stop=42)")


def test_call_tuple_gen(check_ast):
    check_ast("tuple(x for x in [1, 2, 3])")


def test_call_tuple_genifs(check_ast):
    check_ast("tuple(x for x in [1, 2, 3] if x < 3)")


def test_call_range_star(check_ast):
    check_ast("range(*[1, 2, 3])")


def test_call_range_x_star(check_ast):
    check_ast("range(1, *[2, 3])")


def test_call_int(check_ast):
    check_ast('int(*["42"], base=8)')


def test_call_int_base_dict(check_ast):
    check_ast('int(*["42"], **{"base": 8})')


def test_call_dict_kwargs(check_ast):
    check_ast('dict(**{"base": 8})')


def test_call_list_many_star_args(check_ast):
    check_ast("min(*[1, 2], 3, *[4, 5])")


def test_call_list_many_starstar_args(check_ast):
    check_ast('dict(**{"a": 2}, v=3, **{"c": 5})')


def test_call_list_many_star_and_starstar_args(check_ast):
    check_ast('x(*[("a", 2)], *[("v", 3)], **{"c": 5})', False)


def test_call_alot(check_ast):
    check_ast("x(1, *args, **kwargs)", False)


def test_call_alot_next(check_ast):
    check_ast("x(x=1, *args, **kwargs)", False)


def test_call_alot_next_next(check_ast):
    check_ast("x(x=1, *args, y=42, **kwargs)", False)


def test_getattr(check_ast):
    check_ast("list.append")


def test_getattr_getattr(check_ast):
    check_ast("list.append.__str__")


def test_dict_tuple_key(check_ast):
    check_ast("{(42, 1): 65}")


def test_dict_tuple_key_get(check_ast):
    check_ast("{(42, 1): 65}[42, 1]")


def test_dict_tuple_key_get_3(check_ast):
    check_ast("{(42, 1, 3): 65}[42, 1, 3]")


def test_pipe_op(check_ast):
    check_ast("{42} | {65}")


def test_pipe_op_two(check_ast):
    check_ast("{42} | {65} | {1}")


def test_pipe_op_three(check_ast):
    check_ast("{42} | {65} | {1} | {7}")


def test_xor_op(check_ast):
    check_ast("{42} ^ {65}")


def test_xor_op_two(check_ast):
    check_ast("{42} ^ {65} ^ {1}")


def test_xor_op_three(check_ast):
    check_ast("{42} ^ {65} ^ {1} ^ {7}")


def test_xor_pipe(check_ast):
    check_ast("{42} ^ {65} | {1}")


def test_amp_op(check_ast):
    check_ast("{42} & {65}")


def test_amp_op_two(check_ast):
    check_ast("{42} & {65} & {1}")


def test_amp_op_three(check_ast):
    check_ast("{42} & {65} & {1} & {7}")


def test_lshift_op(check_ast):
    check_ast("42 << 65")


def test_lshift_op_two(check_ast):
    check_ast("42 << 65 << 1")


def test_lshift_op_three(check_ast):
    check_ast("42 << 65 << 1 << 7")


def test_rshift_op(check_ast):
    check_ast("42 >> 65")


def test_rshift_op_two(check_ast):
    check_ast("42 >> 65 >> 1")


def test_rshift_op_three(check_ast):
    check_ast("42 >> 65 >> 1 >> 7")


@skip_if_pre_3_8
def test_named_expr(check_ast):
    check_ast("(x := 42)")


@skip_if_pre_3_8
def test_named_expr_list(check_ast):
    check_ast("[x := 42, x + 1, x + 2]")


#
# statements
#


def test_equals(check_stmts):
    check_stmts("x = 42")


def test_equals_semi(check_stmts):
    check_stmts("x = 42;")


def test_x_y_equals_semi(check_stmts):
    check_stmts("x = y = 42")


def test_equals_two(check_stmts):
    check_stmts("x = 42; y = 65")


def test_equals_two_semi(check_stmts):
    check_stmts("x = 42; y = 65;")


def test_equals_three(check_stmts):
    check_stmts("x = 42; y = 65; z = 6")


def test_equals_three_semi(check_stmts):
    check_stmts("x = 42; y = 65; z = 6;")


def test_plus_eq(check_stmts):
    check_stmts("x = 42; x += 65")


def test_sub_eq(check_stmts):
    check_stmts("x = 42; x -= 2")


def test_times_eq(check_stmts):
    check_stmts("x = 42; x *= 2")


def test_matmult_eq(check_stmts):
    check_stmts("x @= y", False)


def test_div_eq(check_stmts):
    check_stmts("x = 42; x /= 2")


def test_floordiv_eq(check_stmts):
    check_stmts("x = 42; x //= 2")


def test_pow_eq(check_stmts):
    check_stmts("x = 42; x **= 2")


def test_mod_eq(check_stmts):
    check_stmts("x = 42; x %= 2")


def test_xor_eq(check_stmts):
    check_stmts("x = 42; x ^= 2")


def test_ampersand_eq(check_stmts):
    check_stmts("x = 42; x &= 2")


def test_bitor_eq(check_stmts):
    check_stmts("x = 42; x |= 2")


def test_lshift_eq(check_stmts):
    check_stmts("x = 42; x <<= 2")


def test_rshift_eq(check_stmts):
    check_stmts("x = 42; x >>= 2")


def test_bare_unpack(check_stmts):
    check_stmts("x, y = 42, 65")


def test_lhand_group_unpack(check_stmts):
    check_stmts("(x, y) = 42, 65")


def test_rhand_group_unpack(check_stmts):
    check_stmts("x, y = (42, 65)")


def test_grouped_unpack(check_stmts):
    check_stmts("(x, y) = (42, 65)")


def test_double_grouped_unpack(check_stmts):
    check_stmts("(x, y) = (z, a) = (7, 8)")


def test_double_ungrouped_unpack(check_stmts):
    check_stmts("x, y = z, a = 7, 8")


def test_stary_eq(check_stmts):
    check_stmts("*y, = [1, 2, 3]")


def test_stary_x(check_stmts):
    check_stmts("*y, x = [1, 2, 3]")


def test_tuple_x_stary(check_stmts):
    check_stmts("(x, *y) = [1, 2, 3]")


def test_list_x_stary(check_stmts):
    check_stmts("[x, *y] = [1, 2, 3]")


def test_bare_x_stary(check_stmts):
    check_stmts("x, *y = [1, 2, 3]")


def test_bare_x_stary_z(check_stmts):
    check_stmts("x, *y, z = [1, 2, 2, 3]")


def test_equals_list(check_stmts):
    check_stmts("x = [42]; x[0] = 65")


def test_equals_dict(check_stmts):
    check_stmts("x = {42: 65}; x[42] = 3")


def test_equals_attr(check_stmts):
    check_stmts("class X(object):\n  pass\nx = X()\nx.a = 65")


def test_equals_annotation(check_stmts):
    check_stmts("x : int = 42")


def test_equals_annotation_empty(check_stmts):
    check_stmts("x : int")


def test_dict_keys(check_stmts):
    check_stmts('x = {"x": 1}\nx.keys()')


def test_assert_msg(check_stmts):
    check_stmts('assert True, "wow mom"')


def test_assert(check_stmts):
    check_stmts("assert True")


def test_pass(check_stmts):
    check_stmts("pass")


def test_del(check_stmts):
    check_stmts("x = 42; del x")


def test_del_comma(check_stmts):
    check_stmts("x = 42; del x,")


def test_del_two(check_stmts):
    check_stmts("x = 42; y = 65; del x, y")


def test_del_two_comma(check_stmts):
    check_stmts("x = 42; y = 65; del x, y,")


def test_del_with_parens(check_stmts):
    check_stmts("x = 42; y = 65; del (x, y)")


def test_raise(check_stmts):
    check_stmts("raise", False)


def test_raise_x(check_stmts):
    check_stmts("raise TypeError", False)


def test_raise_x_from(check_stmts):
    check_stmts("raise TypeError from x", False)


def test_import_x(check_stmts):
    check_stmts("import x", False)


def test_import_xy(check_stmts):
    check_stmts("import x.y", False)


def test_import_xyz(check_stmts):
    check_stmts("import x.y.z", False)


def test_from_x_import_y(check_stmts):
    check_stmts("from x import y", False)


def test_from_dot_import_y(check_stmts):
    check_stmts("from . import y", False)


def test_from_dotx_import_y(check_stmts):
    check_stmts("from .x import y", False)


def test_from_dotdotx_import_y(check_stmts):
    check_stmts("from ..x import y", False)


def test_from_dotdotdotx_import_y(check_stmts):
    check_stmts("from ...x import y", False)


def test_from_dotdotdotdotx_import_y(check_stmts):
    check_stmts("from ....x import y", False)


def test_from_import_x_y(check_stmts):
    check_stmts("import x, y", False)


def test_from_import_x_y_z(check_stmts):
    check_stmts("import x, y, z", False)


def test_from_dot_import_x_y(check_stmts):
    check_stmts("from . import x, y", False)


def test_from_dot_import_x_y_z(check_stmts):
    check_stmts("from . import x, y, z", False)


def test_from_dot_import_group_x_y(check_stmts):
    check_stmts("from . import (x, y)", False)


def test_import_x_as_y(check_stmts):
    check_stmts("import x as y", False)


def test_import_xy_as_z(check_stmts):
    check_stmts("import x.y as z", False)


def test_import_x_y_as_z(check_stmts):
    check_stmts("import x, y as z", False)


def test_import_x_as_y_z(check_stmts):
    check_stmts("import x as y, z", False)


def test_import_x_as_y_z_as_a(check_stmts):
    check_stmts("import x as y, z as a", False)


def test_from_dot_import_x_as_y(check_stmts):
    check_stmts("from . import x as y", False)


def test_from_x_import_star(check_stmts):
    check_stmts("from x import *", False)


def test_from_x_import_group_x_y_z(check_stmts):
    check_stmts("from x import (x, y, z)", False)


def test_from_x_import_group_x_y_z_comma(check_stmts):
    check_stmts("from x import (x, y, z,)", False)


def test_from_x_import_y_as_z(check_stmts):
    check_stmts("from x import y as z", False)


def test_from_x_import_y_as_z_a_as_b(check_stmts):
    check_stmts("from x import y as z, a as b", False)


def test_from_dotx_import_y_as_z_a_as_b_c_as_d(check_stmts):
    check_stmts("from .x import y as z, a as b, c as d", False)


def test_continue(check_stmts):
    check_stmts("continue", False)


def test_break(check_stmts):
    check_stmts("break", False)


def test_global(check_stmts):
    check_stmts("global x", False)


def test_global_xy(check_stmts):
    check_stmts("global x, y", False)


def test_nonlocal_x(check_stmts):
    check_stmts("nonlocal x", False)


def test_nonlocal_xy(check_stmts):
    check_stmts("nonlocal x, y", False)


def test_yield(check_stmts):
    check_stmts("yield", False)


def test_yield_x(check_stmts):
    check_stmts("yield x", False)


def test_yield_x_comma(check_stmts):
    check_stmts("yield x,", False)


def test_yield_x_y(check_stmts):
    check_stmts("yield x, y", False)


@skip_if_pre_3_8
def test_yield_x_starexpr(check_stmts):
    check_stmts("yield x, *[y, z]", False)


def test_yield_from_x(check_stmts):
    check_stmts("yield from x", False)


def test_return(check_stmts):
    check_stmts("return", False)


def test_return_x(check_stmts):
    check_stmts("return x", False)


def test_return_x_comma(check_stmts):
    check_stmts("return x,", False)


def test_return_x_y(check_stmts):
    check_stmts("return x, y", False)


@skip_if_pre_3_8
def test_return_x_starexpr(check_stmts):
    check_stmts("return x, *[y, z]", False)


def test_if_true(check_stmts):
    check_stmts("if True:\n  pass")


def test_if_true_twolines(check_stmts):
    check_stmts("if True:\n  pass\n  pass")


def test_if_true_twolines_deindent(check_stmts):
    check_stmts("if True:\n  pass\n  pass\npass")


def test_if_true_else(check_stmts):
    check_stmts("if True:\n  pass\nelse: \n  pass")


def test_if_true_x(check_stmts):
    check_stmts("if True:\n  x = 42")


def test_if_switch(check_stmts):
    check_stmts("x = 42\nif x == 1:\n  pass")


def test_if_switch_elif1_else(check_stmts):
    check_stmts("x = 42\nif x == 1:\n  pass\n" "elif x == 2:\n  pass\nelse:\n  pass")


def test_if_switch_elif2_else(check_stmts):
    check_stmts(
        "x = 42\nif x == 1:\n  pass\n"
        "elif x == 2:\n  pass\n"
        "elif x == 3:\n  pass\n"
        "elif x == 4:\n  pass\n"
        "else:\n  pass"
    )


def test_if_nested(check_stmts):
    check_stmts("x = 42\nif x == 1:\n  pass\n  if x == 4:\n     pass")


def test_while(check_stmts):
    check_stmts("while False:\n  pass")


def test_while_else(check_stmts):
    check_stmts("while False:\n  pass\nelse:\n  pass")


def test_for(check_stmts):
    check_stmts("for x in range(6):\n  pass")


def test_for_zip(check_stmts):
    check_stmts('for x, y in zip(range(6), "123456"):\n  pass')


def test_for_idx(check_stmts):
    check_stmts("x = [42]\nfor x[0] in range(3):\n  pass")


def test_for_zip_idx(check_stmts):
    check_stmts('x = [42]\nfor x[0], y in zip(range(6), "123456"):\n' "  pass")


def test_for_attr(check_stmts):
    check_stmts("for x.a in range(3):\n  pass", False)


def test_for_zip_attr(check_stmts):
    check_stmts('for x.a, y in zip(range(6), "123456"):\n  pass', False)


def test_for_else(check_stmts):
    check_stmts("for x in range(6):\n  pass\nelse:  pass")


def test_async_for(check_stmts):
    check_stmts("async def f():\n    async for x in y:\n        pass\n", False)


def test_with(check_stmts):
    check_stmts("with x:\n  pass", False)


def test_with_as(check_stmts):
    check_stmts("with x as y:\n  pass", False)


def test_with_xy(check_stmts):
    check_stmts("with x, y:\n  pass", False)


def test_with_x_as_y_z(check_stmts):
    check_stmts("with x as y, z:\n  pass", False)


def test_with_x_as_y_a_as_b(check_stmts):
    check_stmts("with x as y, a as b:\n  pass", False)


def test_with_in_func(check_stmts):
    check_stmts("def f():\n    with x:\n        pass\n")


def test_async_with(check_stmts):
    check_stmts("async def f():\n    async with x as y:\n        pass\n", False)


def test_try(check_stmts):
    check_stmts("try:\n  pass\nexcept:\n  pass", False)


def test_try_except_t(check_stmts):
    check_stmts("try:\n  pass\nexcept TypeError:\n  pass", False)


def test_try_except_t_as_e(check_stmts):
    check_stmts("try:\n  pass\nexcept TypeError as e:\n  pass", False)


def test_try_except_t_u(check_stmts):
    check_stmts("try:\n  pass\nexcept (TypeError, SyntaxError):\n  pass", False)


def test_try_except_t_u_as_e(check_stmts):
    check_stmts("try:\n  pass\nexcept (TypeError, SyntaxError) as e:\n  pass", False)


def test_try_except_t_except_u(check_stmts):
    check_stmts(
        "try:\n  pass\nexcept TypeError:\n  pass\n" "except SyntaxError as f:\n  pass",
        False,
    )


def test_try_except_else(check_stmts):
    check_stmts("try:\n  pass\nexcept:\n  pass\nelse:  pass", False)


def test_try_except_finally(check_stmts):
    check_stmts("try:\n  pass\nexcept:\n  pass\nfinally:  pass", False)


def test_try_except_else_finally(check_stmts):
    check_stmts(
        "try:\n  pass\nexcept:\n  pass\nelse:\n  pass" "\nfinally:  pass", False
    )


def test_try_finally(check_stmts):
    check_stmts("try:\n  pass\nfinally:  pass", False)


def test_func(check_stmts):
    check_stmts("def f():\n  pass")


def test_func_ret(check_stmts):
    check_stmts("def f():\n  return")


def test_func_ret_42(check_stmts):
    check_stmts("def f():\n  return 42")


def test_func_ret_42_65(check_stmts):
    check_stmts("def f():\n  return 42, 65")


def test_func_rarrow(check_stmts):
    check_stmts("def f() -> int:\n  pass")


def test_func_x(check_stmts):
    check_stmts("def f(x):\n  return x")


def test_func_kwx(check_stmts):
    check_stmts("def f(x=42):\n  return x")


def test_func_x_y(check_stmts):
    check_stmts("def f(x, y):\n  return x")


def test_func_x_y_z(check_stmts):
    check_stmts("def f(x, y, z):\n  return x")


def test_func_x_kwy(check_stmts):
    check_stmts("def f(x, y=42):\n  return x")


def test_func_kwx_kwy(check_stmts):
    check_stmts("def f(x=65, y=42):\n  return x")


def test_func_kwx_kwy_kwz(check_stmts):
    check_stmts("def f(x=65, y=42, z=1):\n  return x")


def test_func_x_comma(check_stmts):
    check_stmts("def f(x,):\n  return x")


def test_func_x_y_comma(check_stmts):
    check_stmts("def f(x, y,):\n  return x")


def test_func_x_y_z_comma(check_stmts):
    check_stmts("def f(x, y, z,):\n  return x")


def test_func_x_kwy_comma(check_stmts):
    check_stmts("def f(x, y=42,):\n  return x")


def test_func_kwx_kwy_comma(check_stmts):
    check_stmts("def f(x=65, y=42,):\n  return x")


def test_func_kwx_kwy_kwz_comma(check_stmts):
    check_stmts("def f(x=65, y=42, z=1,):\n  return x")


def test_func_args(check_stmts):
    check_stmts("def f(*args):\n  return 42")


def test_func_args_x(check_stmts):
    check_stmts("def f(*args, x):\n  return 42")


def test_func_args_x_y(check_stmts):
    check_stmts("def f(*args, x, y):\n  return 42")


def test_func_args_x_kwy(check_stmts):
    check_stmts("def f(*args, x, y=10):\n  return 42")


def test_func_args_kwx_y(check_stmts):
    check_stmts("def f(*args, x=10, y):\n  return 42")


def test_func_args_kwx_kwy(check_stmts):
    check_stmts("def f(*args, x=42, y=65):\n  return 42")


def test_func_x_args(check_stmts):
    check_stmts("def f(x, *args):\n  return 42")


def test_func_x_args_y(check_stmts):
    check_stmts("def f(x, *args, y):\n  return 42")


def test_func_x_args_y_z(check_stmts):
    check_stmts("def f(x, *args, y, z):\n  return 42")


def test_func_kwargs(check_stmts):
    check_stmts("def f(**kwargs):\n  return 42")


def test_func_x_kwargs(check_stmts):
    check_stmts("def f(x, **kwargs):\n  return 42")


def test_func_x_y_kwargs(check_stmts):
    check_stmts("def f(x, y, **kwargs):\n  return 42")


def test_func_x_kwy_kwargs(check_stmts):
    check_stmts("def f(x, y=42, **kwargs):\n  return 42")


def test_func_args_kwargs(check_stmts):
    check_stmts("def f(*args, **kwargs):\n  return 42")


def test_func_x_args_kwargs(check_stmts):
    check_stmts("def f(x, *args, **kwargs):\n  return 42")


def test_func_x_y_args_kwargs(check_stmts):
    check_stmts("def f(x, y, *args, **kwargs):\n  return 42")


def test_func_kwx_args_kwargs(check_stmts):
    check_stmts("def f(x=10, *args, **kwargs):\n  return 42")


def test_func_x_kwy_args_kwargs(check_stmts):
    check_stmts("def f(x, y=42, *args, **kwargs):\n  return 42")


def test_func_x_args_y_kwargs(check_stmts):
    check_stmts("def f(x, *args, y, **kwargs):\n  return 42")


def test_func_x_args_kwy_kwargs(check_stmts):
    check_stmts("def f(x, *args, y=42, **kwargs):\n  return 42")


def test_func_args_y_kwargs(check_stmts):
    check_stmts("def f(*args, y, **kwargs):\n  return 42")


def test_func_star_x(check_stmts):
    check_stmts("def f(*, x):\n  return 42")


def test_func_star_x_y(check_stmts):
    check_stmts("def f(*, x, y):\n  return 42")


def test_func_star_x_kwargs(check_stmts):
    check_stmts("def f(*, x, **kwargs):\n  return 42")


def test_func_star_kwx_kwargs(check_stmts):
    check_stmts("def f(*, x=42, **kwargs):\n  return 42")


def test_func_x_star_y(check_stmts):
    check_stmts("def f(x, *, y):\n  return 42")


def test_func_x_y_star_z(check_stmts):
    check_stmts("def f(x, y, *, z):\n  return 42")


def test_func_x_kwy_star_y(check_stmts):
    check_stmts("def f(x, y=42, *, z):\n  return 42")


def test_func_x_kwy_star_kwy(check_stmts):
    check_stmts("def f(x, y=42, *, z=65):\n  return 42")


def test_func_x_star_y_kwargs(check_stmts):
    check_stmts("def f(x, *, y, **kwargs):\n  return 42")


@skip_if_pre_3_8
def test_func_x_divide(check_stmts):
    check_stmts("def f(x, /):\n  return 42")


@skip_if_pre_3_8
def test_func_x_divide_y_star_z_kwargs(check_stmts):
    check_stmts("def f(x, /, y, *, z, **kwargs):\n  return 42")


def test_func_tx(check_stmts):
    check_stmts("def f(x:int):\n  return x")


def test_func_txy(check_stmts):
    check_stmts("def f(x:int, y:float=10.0):\n  return x")


def test_class(check_stmts):
    check_stmts("class X:\n  pass")


def test_class_obj(check_stmts):
    check_stmts("class X(object):\n  pass")


def test_class_int_flt(check_stmts):
    check_stmts("class X(int, object):\n  pass")


def test_class_obj_kw(check_stmts):
    # technically valid syntax, though it will fail to compile
    check_stmts("class X(object=5):\n  pass", False)


def test_decorator(check_stmts):
    check_stmts("@g\ndef f():\n  pass", False)


def test_decorator_2(check_stmts):
    check_stmts("@h\n@g\ndef f():\n  pass", False)


def test_decorator_call(check_stmts):
    check_stmts("@g()\ndef f():\n  pass", False)


def test_decorator_call_args(check_stmts):
    check_stmts("@g(x, y=10)\ndef f():\n  pass", False)


def test_decorator_dot_call_args(check_stmts):
    check_stmts("@h.g(x, y=10)\ndef f():\n  pass", False)


def test_decorator_dot_dot_call_args(check_stmts):
    check_stmts("@i.h.g(x, y=10)\ndef f():\n  pass", False)


def test_broken_prompt_func(check_stmts):
    code = "def prompt():\n" "    return '{user}'.format(\n" "       user='me')\n"
    check_stmts(code, False)


def test_class_with_methods(check_stmts):
    code = (
        "class Test:\n"
        "   def __init__(self):\n"
        '       self.msg("hello world")\n'
        "   def msg(self, m):\n"
        "      print(m)\n"
    )
    check_stmts(code, False)


def test_nested_functions(check_stmts):
    code = (
        "def test(x):\n"
        "    def test2(y):\n"
        "        return y+x\n"
        "    return test2\n"
    )
    check_stmts(code, False)


def test_function_blank_line(check_stmts):
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


def test_async_func(check_stmts):
    check_stmts("async def f():\n  pass\n")


def test_async_decorator(check_stmts):
    check_stmts("@g\nasync def f():\n  pass", False)


def test_async_await(check_stmts):
    check_stmts("async def f():\n    await fut\n", False)


@skip_if_pre_3_8
def test_named_expr_args(check_stmts):
    check_stmts("id(x := 42)")


@skip_if_pre_3_8
def test_named_expr_if(check_stmts):
    check_stmts("if (x := 42) > 0:\n  x += 1")


@skip_if_pre_3_8
def test_named_expr_elif(check_stmts):
    check_stmts("if False:\n  pass\nelif x := 42:\n  x += 1")


@skip_if_pre_3_8
def test_named_expr_while(check_stmts):
    check_stmts("y = 42\nwhile (x := y) < 43:\n  y += 1")


#
# Xonsh specific syntax
#


def test_path_literal(check_xonsh_ast):
    check_xonsh_ast({}, 'p"/foo"', False)
    check_xonsh_ast({}, 'pr"/foo"', False)
    check_xonsh_ast({}, 'rp"/foo"', False)
    check_xonsh_ast({}, 'pR"/foo"', False)
    check_xonsh_ast({}, 'Rp"/foo"', False)


def test_path_fstring_literal(check_xonsh_ast):
    check_xonsh_ast({}, 'pf"/foo"', False)
    check_xonsh_ast({}, 'fp"/foo"', False)
    check_xonsh_ast({}, 'pF"/foo"', False)
    check_xonsh_ast({}, 'Fp"/foo"', False)
    check_xonsh_ast({}, 'pf"/foo{1+1}"', False)
    check_xonsh_ast({}, 'fp"/foo{1+1}"', False)
    check_xonsh_ast({}, 'pF"/foo{1+1}"', False)
    check_xonsh_ast({}, 'Fp"/foo{1+1}"', False)


@pytest.mark.parametrize(
    "first_prefix, second_prefix",
    itertools.product(["p", "pf", "pr"], repeat=2),
)
def test_path_literal_concat(first_prefix, second_prefix, check_xonsh_ast):
    check_xonsh_ast(
        {}, first_prefix + r"'11{a}22\n'" + " " + second_prefix + r"'33{b}44\n'", False
    )


def test_dollar_name(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": 42}, "$WAKKA")


def test_dollar_py(check_xonsh):
    check_xonsh({"WAKKA": 42}, 'x = "WAKKA"; y = ${x}')


def test_dollar_py_test(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": 42}, '${None or "WAKKA"}')


def test_dollar_py_recursive_name(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, "${$JAWAKA}")


def test_dollar_py_test_recursive_name(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, "${None or $JAWAKA}")


def test_dollar_py_test_recursive_test(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": 42, "JAWAKA": "WAKKA"}, '${${"JAWA" + $JAWAKA[-2:]}}')


def test_dollar_name_set(check_xonsh):
    check_xonsh({"WAKKA": 42}, "$WAKKA = 42")


def test_dollar_py_set(check_xonsh):
    check_xonsh({"WAKKA": 42}, 'x = "WAKKA"; ${x} = 65')


def test_dollar_sub(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls)", False)


@pytest.mark.parametrize(
    "expr",
    [
        "$(ls )",
        "$( ls)",
        "$( ls )",
    ],
)
def test_dollar_sub_space(expr, check_xonsh_ast):
    check_xonsh_ast({}, expr, False)


def test_ls_dot(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls .)", False)


def test_lambda_in_atparens(check_xonsh_ast):
    check_xonsh_ast(
        {}, '$(echo hello | @(lambda a, s=None: "hey!") foo bar baz)', False
    )


def test_generator_in_atparens(check_xonsh_ast):
    check_xonsh_ast({}, "$(echo @(i**2 for i in range(20)))", False)


def test_bare_tuple_in_atparens(check_xonsh_ast):
    check_xonsh_ast({}, '$(echo @("a", 7))', False)


def test_nested_madness(check_xonsh_ast):
    check_xonsh_ast(
        {},
        "$(@$(which echo) ls | @(lambda a, s=None: $(@(s.strip()) @(a[1]))) foo -la baz)",
        False,
    )


def test_atparens_intoken(check_xonsh_ast):
    check_xonsh_ast({}, "![echo /x/@(y)/z]", False)


def test_ls_dot_nesting(check_xonsh_ast):
    check_xonsh_ast({}, '$(ls @(None or "."))', False)


def test_ls_dot_nesting_var(check_xonsh):
    check_xonsh({}, 'x = "."; $(ls @(None or x))', False)


def test_ls_dot_str(check_xonsh_ast):
    check_xonsh_ast({}, '$(ls ".")', False)


def test_ls_nest_ls(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls $(ls))", False)


def test_ls_nest_ls_dashl(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls $(ls) -l)", False)


def test_ls_envvar_strval(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": "."}, "$(ls $WAKKA)", False)


def test_ls_envvar_listval(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": [".", "."]}, "$(ls $WAKKA)", False)


def test_bang_sub(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls)", False)


@pytest.mark.parametrize(
    "expr",
    [
        "!(ls )",
        "!( ls)",
        "!( ls )",
    ],
)
def test_bang_sub_space(expr, check_xonsh_ast):
    check_xonsh_ast({}, expr, False)


def test_bang_ls_dot(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls .)", False)


def test_bang_ls_dot_nesting(check_xonsh_ast):
    check_xonsh_ast({}, '!(ls @(None or "."))', False)


def test_bang_ls_dot_nesting_var(check_xonsh):
    check_xonsh({}, 'x = "."; !(ls @(None or x))', False)


def test_bang_ls_dot_str(check_xonsh_ast):
    check_xonsh_ast({}, '!(ls ".")', False)


def test_bang_ls_nest_ls(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls $(ls))", False)


def test_bang_ls_nest_ls_dashl(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls $(ls) -l)", False)


def test_bang_ls_envvar_strval(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": "."}, "!(ls $WAKKA)", False)


def test_bang_ls_envvar_listval(check_xonsh_ast):
    check_xonsh_ast({"WAKKA": [".", "."]}, "!(ls $WAKKA)", False)


def test_bang_envvar_args(check_xonsh_ast):
    check_xonsh_ast({"LS": "ls"}, "!($LS .)", False)


def test_question(check_xonsh_ast):
    check_xonsh_ast({}, "range?")


def test_dobquestion(check_xonsh_ast):
    check_xonsh_ast({}, "range??")


def test_question_chain(check_xonsh_ast):
    check_xonsh_ast({}, "range?.index?")


def test_ls_regex(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls `[Ff]+i*LE` -l)", False)


@pytest.mark.parametrize("p", ["", "p"])
@pytest.mark.parametrize("f", ["", "f"])
@pytest.mark.parametrize("glob_type", ["", "r", "g"])
def test_backtick(p, f, glob_type, check_xonsh_ast):
    check_xonsh_ast({}, f"print({p}{f}{glob_type}`.*`)", False)


def test_ls_regex_octothorpe(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls `#[Ff]+i*LE` -l)", False)


def test_ls_explicitregex(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls r`[Ff]+i*LE` -l)", False)


def test_ls_explicitregex_octothorpe(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls r`#[Ff]+i*LE` -l)", False)


def test_ls_glob(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls g`[Ff]+i*LE` -l)", False)


def test_ls_glob_octothorpe(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls g`#[Ff]+i*LE` -l)", False)


def test_ls_customsearch(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls @foo`[Ff]+i*LE` -l)", False)


def test_custombacktick(check_xonsh_ast):
    check_xonsh_ast({}, "print(@foo`.*`)", False)


def test_ls_customsearch_octothorpe(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls @foo`#[Ff]+i*LE` -l)", False)


def test_injection(check_xonsh_ast):
    check_xonsh_ast({}, "$[@$(which python)]", False)


def test_rhs_nested_injection(check_xonsh_ast):
    check_xonsh_ast({}, "$[ls @$(dirname @$(which python))]", False)


def test_merged_injection(check_xonsh_ast):
    tree = check_xonsh_ast({}, "![a@$(echo 1 2)b]", False, return_obs=True)
    assert isinstance(tree, AST)
    func = tree.body.args[0].right.func
    assert func.attr == "list_of_list_of_strs_outer_product"


def test_backtick_octothorpe(check_xonsh_ast):
    check_xonsh_ast({}, "print(`#.*`)", False)


def test_uncaptured_sub(check_xonsh_ast):
    check_xonsh_ast({}, "$[ls]", False)


def test_hiddenobj_sub(check_xonsh_ast):
    check_xonsh_ast({}, "![ls]", False)


def test_slash_envarv_echo(check_xonsh_ast):
    check_xonsh_ast({}, "![echo $HOME/place]", False)


def test_echo_double_eq(check_xonsh_ast):
    check_xonsh_ast({}, "![echo yo==yo]", False)


def test_bang_two_cmds_one_pipe(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls | grep wakka)", False)


def test_bang_three_cmds_two_pipes(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls | grep wakka | grep jawaka)", False)


def test_bang_one_cmd_write(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls > x.py)", False)


def test_bang_one_cmd_append(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls >> x.py)", False)


def test_bang_two_cmds_write(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls | grep wakka > x.py)", False)


def test_bang_two_cmds_append(check_xonsh_ast):
    check_xonsh_ast({}, "!(ls | grep wakka >> x.py)", False)


def test_bang_cmd_background(check_xonsh_ast):
    check_xonsh_ast({}, "!(emacs ugggh &)", False)


def test_bang_cmd_background_nospace(check_xonsh_ast):
    check_xonsh_ast({}, "!(emacs ugggh&)", False)


def test_bang_git_quotes_no_space(check_xonsh_ast):
    check_xonsh_ast({}, '![git commit -am "wakka"]', False)


def test_bang_git_quotes_space(check_xonsh_ast):
    check_xonsh_ast({}, '![git commit -am "wakka jawaka"]', False)


def test_bang_git_two_quotes_space(check_xonsh):
    check_xonsh(
        {},
        '![git commit -am "wakka jawaka"]\n' '![git commit -am "flock jawaka"]\n',
        False,
    )


def test_bang_git_two_quotes_space_space(check_xonsh):
    check_xonsh(
        {},
        '![git commit -am "wakka jawaka" ]\n'
        '![git commit -am "flock jawaka milwaka" ]\n',
        False,
    )


def test_bang_ls_quotes_3_space(check_xonsh_ast):
    check_xonsh_ast({}, '![ls "wakka jawaka baraka"]', False)


def test_two_cmds_one_pipe(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls | grep wakka)", False)


def test_three_cmds_two_pipes(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls | grep wakka | grep jawaka)", False)


def test_two_cmds_one_and_brackets(check_xonsh_ast):
    check_xonsh_ast({}, "![ls me] and ![grep wakka]", False)


def test_three_cmds_two_ands(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] and ![grep wakka] and ![grep jawaka]", False)


def test_two_cmds_one_doubleamps(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] && ![grep wakka]", False)


def test_three_cmds_two_doubleamps(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] && ![grep wakka] && ![grep jawaka]", False)


def test_two_cmds_one_or(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] or ![grep wakka]", False)


def test_three_cmds_two_ors(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] or ![grep wakka] or ![grep jawaka]", False)


def test_two_cmds_one_doublepipe(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] || ![grep wakka]", False)


def test_three_cmds_two_doublepipe(check_xonsh_ast):
    check_xonsh_ast({}, "![ls] || ![grep wakka] || ![grep jawaka]", False)


def test_one_cmd_write(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls > x.py)", False)


def test_one_cmd_append(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls >> x.py)", False)


def test_two_cmds_write(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls | grep wakka > x.py)", False)


def test_two_cmds_append(check_xonsh_ast):
    check_xonsh_ast({}, "$(ls | grep wakka >> x.py)", False)


def test_cmd_background(check_xonsh_ast):
    check_xonsh_ast({}, "$(emacs ugggh &)", False)


def test_cmd_background_nospace(check_xonsh_ast):
    check_xonsh_ast({}, "$(emacs ugggh&)", False)


def test_git_quotes_no_space(check_xonsh_ast):
    check_xonsh_ast({}, '$[git commit -am "wakka"]', False)


def test_git_quotes_space(check_xonsh_ast):
    check_xonsh_ast({}, '$[git commit -am "wakka jawaka"]', False)


def test_git_two_quotes_space(check_xonsh):
    check_xonsh(
        {},
        '$[git commit -am "wakka jawaka"]\n' '$[git commit -am "flock jawaka"]\n',
        False,
    )


def test_git_two_quotes_space_space(check_xonsh):
    check_xonsh(
        {},
        '$[git commit -am "wakka jawaka" ]\n'
        '$[git commit -am "flock jawaka milwaka" ]\n',
        False,
    )


def test_ls_quotes_3_space(check_xonsh_ast):
    check_xonsh_ast({}, '$[ls "wakka jawaka baraka"]', False)


def test_leading_envvar_assignment(check_xonsh_ast):
    check_xonsh_ast({}, "![$FOO='foo' $BAR=2 echo r'$BAR']", False)


def test_echo_comma(check_xonsh_ast):
    check_xonsh_ast({}, "![echo ,]", False)


def test_echo_internal_comma(check_xonsh_ast):
    check_xonsh_ast({}, "![echo 1,2]", False)


def test_comment_only(check_xonsh_ast):
    check_xonsh_ast({}, "# hello")


def test_echo_slash_question(check_xonsh_ast):
    check_xonsh_ast({}, "![echo /?]", False)


def test_bad_quotes(check_xonsh_ast):
    with pytest.raises(SyntaxError):
        check_xonsh_ast({}, '![echo """hello]', False)


def test_redirect(check_xonsh_ast):
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
def test_use_subshell(case, check_xonsh_ast):
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
def test_redirect_abspath(case, check_xonsh_ast):
    assert check_xonsh_ast({}, case, False)


@pytest.mark.parametrize("case", ["", "o", "out", "1"])
def test_redirect_output(case, check_xonsh_ast):
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[< input.txt echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt < input.txt]', False)


@pytest.mark.parametrize("case", ["e", "err", "2"])
def test_redirect_error(case, check_xonsh_ast):
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[< input.txt echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt < input.txt]', False)


@pytest.mark.parametrize("case", ["a", "all", "&"])
def test_redirect_all(case, check_xonsh_ast):
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[< input.txt echo "test" {case}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[echo "test" {case}> test.txt < input.txt]', False)


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
def test_redirect_error_to_output(r, o, check_xonsh_ast):
    assert check_xonsh_ast({}, f'$[echo "test" {r} {o}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[< input.txt echo "test" {r} {o}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[echo "test" {r} {o}> test.txt < input.txt]', False)


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
def test_redirect_output_to_error(r, e, check_xonsh_ast):
    assert check_xonsh_ast({}, f'$[echo "test" {r} {e}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[< input.txt echo "test" {r} {e}> test.txt]', False)
    assert check_xonsh_ast({}, f'$[echo "test" {r} {e}> test.txt < input.txt]', False)


def test_macro_call_empty(check_xonsh_ast):
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
def test_macro_call_one_arg(check_xonsh_ast, s):
    f = f"f!({s})"
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


@pytest.mark.parametrize("s,t", itertools.product(MACRO_ARGS[::2], MACRO_ARGS[1::2]))
def test_macro_call_two_args(check_xonsh_ast, s, t):
    f = f"f!({s}, {t})"
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 2
    assert args[0].s == s.strip()
    assert args[1].s == t.strip()


@pytest.mark.parametrize(
    "s,t,u", itertools.product(MACRO_ARGS[::3], MACRO_ARGS[1::3], MACRO_ARGS[2::3])
)
def test_macro_call_three_args(check_xonsh_ast, s, t, u):
    f = f"f!({s}, {t}, {u})"
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 3
    assert args[0].s == s.strip()
    assert args[1].s == t.strip()
    assert args[2].s == u.strip()


@pytest.mark.parametrize("s", MACRO_ARGS)
def test_macro_call_one_trailing(check_xonsh_ast, s):
    f = f"f!({s},)"
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


@pytest.mark.parametrize("s", MACRO_ARGS)
def test_macro_call_one_trailing_space(check_xonsh_ast, s):
    f = f"f!( {s}, )"
    tree = check_xonsh_ast({}, f, False, return_obs=True)
    assert isinstance(tree, AST)
    args = tree.body.args[1].elts
    assert len(args) == 1
    assert args[0].s == s.strip()


SUBPROC_MACRO_OC = [("!(", ")"), ("$(", ")"), ("![", "]"), ("$[", "]")]


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize("body", ["echo!", "echo !", "echo ! "])
def test_empty_subprocbang(opener, closer, body, check_xonsh_ast):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 2
    assert cmd[1].s == ""


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize("body", ["echo!x", "echo !x", "echo !x", "echo ! x"])
def test_single_subprocbang(opener, closer, body, check_xonsh_ast):
    tree = check_xonsh_ast({}, opener + body + closer, False, return_obs=True)
    assert isinstance(tree, AST)
    cmd = tree.body.args[0].elts
    assert len(cmd) == 2
    assert cmd[1].s == "x"


@pytest.mark.parametrize("opener, closer", SUBPROC_MACRO_OC)
@pytest.mark.parametrize(
    "body", ["echo -n!x", "echo -n!x", "echo -n !x", "echo -n ! x"]
)
def test_arg_single_subprocbang(opener, closer, body, check_xonsh_ast):
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
def test_arg_single_subprocbang_nested(
    opener, closer, ipener, iloser, body, check_xonsh_ast
):
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
def test_many_subprocbang(opener, closer, body, check_xonsh_ast):
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
def test_withbang_single_suite(body, check_xonsh_ast):
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
def test_withbang_as_single_suite(body, check_xonsh_ast):
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
def test_withbang_single_suite_trailing(body, check_xonsh_ast):
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
def test_withbang_single_simple(body, check_xonsh_ast):
    code = f"with! x: {body}\n"
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
def test_withbang_single_simple_opt(body, check_xonsh_ast):
    code = f"with! x as y: {body}\n"
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
def test_withbang_as_many_suite(body, check_xonsh_ast):
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


def test_subproc_raw_str_literal(check_xonsh_ast):
    tree = check_xonsh_ast({}, "!(echo '$foo')", run=False, return_obs=True)
    assert isinstance(tree, AST)
    subproc = tree.body
    assert isinstance(subproc.args[0].elts[1], Call)
    assert subproc.args[0].elts[1].func.attr == "expand_path"

    tree = check_xonsh_ast({}, "!(echo r'$foo')", run=False, return_obs=True)
    assert isinstance(tree, AST)
    subproc = tree.body
    assert isinstance(subproc.args[0].elts[1], Str)
    assert subproc.args[0].elts[1].s == "$foo"


# test invalid expressions


def test_syntax_error_del_literal(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del 7")


def test_syntax_error_del_constant(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del True")


def test_syntax_error_del_emptytuple(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del ()")


def test_syntax_error_del_call(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del foo()")


def test_syntax_error_del_lambda(parser):
    with pytest.raises(SyntaxError):
        parser.parse('del lambda x: "yay"')


def test_syntax_error_del_ifexp(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del x if y else z")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_del_comps(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"del {exp}")


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_del_ops(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"del {exp}")


@pytest.mark.parametrize("exp", ["x > y", "x > y == z"])
def test_syntax_error_del_cmp(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"del {exp}")


def test_syntax_error_lonely_del(parser):
    with pytest.raises(SyntaxError):
        parser.parse("del")


def test_syntax_error_assign_literal(parser):
    with pytest.raises(SyntaxError):
        parser.parse("7 = x")


def test_syntax_error_assign_constant(parser):
    with pytest.raises(SyntaxError):
        parser.parse("True = 8")


def test_syntax_error_assign_emptytuple(parser):
    with pytest.raises(SyntaxError):
        parser.parse("() = x")


def test_syntax_error_assign_call(parser):
    with pytest.raises(SyntaxError):
        parser.parse("foo() = x")


def test_syntax_error_assign_lambda(parser):
    with pytest.raises(SyntaxError):
        parser.parse('lambda x: "yay" = y')


def test_syntax_error_assign_ifexp(parser):
    with pytest.raises(SyntaxError):
        parser.parse("x if y else z = 8")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_assign_comps(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} = z")


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_assign_ops(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} = z")


@pytest.mark.parametrize("exp", ["x > y", "x > y == z"])
def test_syntax_error_assign_cmp(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} = a")


def test_syntax_error_augassign_literal(parser):
    with pytest.raises(SyntaxError):
        parser.parse("7 += x")


def test_syntax_error_augassign_constant(parser):
    with pytest.raises(SyntaxError):
        parser.parse("True += 8")


def test_syntax_error_augassign_emptytuple(parser):
    with pytest.raises(SyntaxError):
        parser.parse("() += x")


def test_syntax_error_augassign_call(parser):
    with pytest.raises(SyntaxError):
        parser.parse("foo() += x")


def test_syntax_error_augassign_lambda(parser):
    with pytest.raises(SyntaxError):
        parser.parse('lambda x: "yay" += y')


def test_syntax_error_augassign_ifexp(parser):
    with pytest.raises(SyntaxError):
        parser.parse("x if y else z += 8")


@pytest.mark.parametrize(
    "exp",
    [
        "[i for i in foo]",
        "{i for i in foo}",
        "(i for i in foo)",
        "{k:v for k,v in d.items()}",
    ],
)
def test_syntax_error_augassign_comps(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} += z")


@pytest.mark.parametrize("exp", ["x + y", "x and y", "-x"])
def test_syntax_error_augassign_ops(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} += z")


@pytest.mark.parametrize("exp", ["x > y", "x > y +=+= z"])
def test_syntax_error_augassign_cmp(parser, exp):
    with pytest.raises(SyntaxError):
        parser.parse(f"{exp} += a")


def test_syntax_error_bar_kwonlyargs(parser):
    with pytest.raises(SyntaxError):
        parser.parse("def spam(*):\n   pass\n", mode="exec")


@skip_if_pre_3_8
def test_syntax_error_bar_posonlyargs(parser):
    with pytest.raises(SyntaxError):
        parser.parse("def spam(/):\n   pass\n", mode="exec")


@skip_if_pre_3_8
def test_syntax_error_bar_posonlyargs_no_comma(parser):
    with pytest.raises(SyntaxError):
        parser.parse("def spam(x /, y):\n   pass\n", mode="exec")


def test_syntax_error_nondefault_follows_default(parser):
    with pytest.raises(SyntaxError):
        parser.parse("def spam(x=1, y):\n   pass\n", mode="exec")


@skip_if_pre_3_8
def test_syntax_error_posonly_nondefault_follows_default(parser):
    with pytest.raises(SyntaxError):
        parser.parse("def spam(x, y=1, /, z):\n   pass\n", mode="exec")


def test_syntax_error_lambda_nondefault_follows_default(parser):
    with pytest.raises(SyntaxError):
        parser.parse("lambda x=1, y: x", mode="exec")


@skip_if_pre_3_8
def test_syntax_error_lambda_posonly_nondefault_follows_default(parser):
    with pytest.raises(SyntaxError):
        parser.parse("lambda x, y=1, /, z: x", mode="exec")


@pytest.mark.parametrize(
    "first_prefix, second_prefix", itertools.permutations(["", "p", "b"], 2)
)
def test_syntax_error_literal_concat_different(first_prefix, second_prefix, parser):
    with pytest.raises(SyntaxError):
        parser.parse(f"{first_prefix}'hello' {second_prefix}'world'")


def test_get_repo_url(parser):
    parser.parse(
        "def get_repo_url():\n"
        "    raw = $(git remote get-url --push origin).rstrip()\n"
        "    return raw.replace('https://github.com/', '')\n"
    )


# match statement
# (tests asserting that pure python match statements produce the same ast with the xonsh parser as they do with the python parser)


def test_match_and_case_are_not_keywords(check_stmts):
    check_stmts(
        """
match = 1
case = 2
def match():
    pass
class case():
    pass
"""
    )


@skip_if_pre_3_10
def test_match_literal_pattern(check_stmts):
    check_stmts(
        """match 1:
    case 1j:
        pass
    case 2.718+3.141j:
        pass
    case -2.718-3.141j:
        pass
    case 2:
        pass
    case -2:
        pass
    case "One" 'Two':
        pass
    case None:
        pass
    case True:
        pass
    case False:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_or_pattern(check_stmts):
    check_stmts(
        """match 1:
    case 1j | 2 | "One" | 'Two' | None | True | False:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_as_pattern(check_stmts):
    check_stmts(
        """match 1:
    case 1j | 2 | "One" | 'Two' | None | True | False as target:
        pass
    case 2 as target:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_group_pattern(check_stmts):
    check_stmts(
        """match 1:
    case (None):
        pass
    case ((None)):
        pass
    case (1 | 2 as x) as x:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_capture_and_wildcard_pattern(check_stmts):
    check_stmts(
        """match 1:
    case _:
        pass
    case x:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_value_pattern(check_stmts):
    check_stmts(
        """match 1:
    case math.pi:
        pass
    case a.b.c.d:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_mapping_pattern(check_stmts):
    check_stmts(
        """match _:
    case {}:
        pass
    case {x.y:y}:
        pass
    case {x.y:y,}:
        pass
    case {x.y:y,"a":a}:
        pass
    case {x.y:y,"a":a,}:
        pass
    case {x.y:y,"a":a,**end}:
        pass
    case {x.y:y,"a":a,**end,}:
        pass
    case {**end}:
        pass
    case {**end,}:
        pass
    case {1:1, "two":two, three.three: {}, 4:None, **end}:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_class_pattern(check_stmts):
    check_stmts(
        """match _:
    case classs():
        pass
    case x.classs():
        pass
    case classs("subpattern"):
        pass
    case classs("subpattern",):
        pass
    case classs("subpattern",2):
        pass
    case classs("subpattern",2,):
        pass
    case classs(a = b):
        pass
    case classs(a = b,):
        pass
    case classs(a = b, b = c):
        pass
    case classs(a = b, b = c,):
        pass
    case classs(1,2,3,a = b):
        pass
    case classs(1,2,3,a = b,):
        pass
    case classs(1,2,3,a = b, b = c):
        pass
    case classs(1,2,3,a = b, b = c,):
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_sequence_pattern(check_stmts):
    check_stmts(
        """match 1:
    case (): # empty sequence pattern
        pass
    case (1): # group pattern
        pass
    case (1,): # length one sequence
        pass
    case (1,2):
        pass
    case (1,2,):
        pass
    case (1,2,3):
        pass
    case (1,2,3,):
        pass
    case []:
        pass
    case [1]:
        pass
    case [1,]:
        pass
    case [1,2]:
        pass
    case [1,2,3]:
        pass
    case [1,2,3,]:
        pass
    case [*x, *_]: # star patterns
        pass
    case 1,: # top level sequence patterns
        pass
    case *x,:
        pass
    case *_,*_:
        pass
""",
        run=False,
    )


@skip_if_pre_3_10
def test_match_subject(check_stmts):
    check_stmts(
        """
match 1:
    case 1:
        pass
match 1,:
    case 1:
        pass
match 1,2:
    case 1:
        pass
match 1,2,:
    case 1:
        pass
match (1,2):
    case 1:
        pass
match *x,:
    case 1:
        pass
match (...[...][...]):
    case 1:
        pass
""",
        run=False,
    )
