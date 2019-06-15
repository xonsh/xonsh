# -*- coding: utf-8 -*-
"""Tests xonsh tools."""
import datetime as dt
import os
import pathlib
import stat
from tempfile import TemporaryDirectory
import warnings

import pytest

from xonsh import __version__
from xonsh.platform import ON_WINDOWS
from xonsh.lexer import Lexer

from xonsh.tools import (
    EnvPath,
    always_false,
    always_true,
    argvquote,
    bool_or_int_to_str,
    bool_to_str,
    check_for_partial_string,
    dynamic_cwd_tuple_to_str,
    ensure_slice,
    ensure_string,
    env_path_to_str,
    escape_windows_cmd_string,
    executables_in,
    expand_case_matching,
    expand_path,
    find_next_break,
    is_bool,
    is_bool_or_int,
    is_callable,
    is_dynamic_cwd_width,
    is_env_path,
    is_float,
    is_int,
    is_logfile_opt,
    is_string_or_callable,
    logfile_opt_to_str,
    str_to_env_path,
    is_string,
    subexpr_from_unbalanced,
    subproc_toks,
    to_bool,
    to_bool_or_int,
    to_dynamic_cwd_tuple,
    to_logfile_opt,
    pathsep_to_set,
    set_to_pathsep,
    is_string_seq,
    pathsep_to_seq,
    seq_to_pathsep,
    is_nonstring_seq_of_strings,
    pathsep_to_upper_seq,
    seq_to_upper_pathsep,
    expandvars,
    is_int_as_str,
    is_slice_as_str,
    ensure_timestamp,
    get_portions,
    is_balanced,
    subexpr_before_unbalanced,
    swap_values,
    get_line_continuation,
    get_logical_line,
    replace_logical_line,
    check_quotes,
    deprecated,
    is_writable_file,
    balanced_parens,
    iglobpath,
    all_permutations,
)
from xonsh.environ import Env

from tools import skip_if_on_windows, skip_if_on_unix

LEXER = Lexer()
LEXER.build()

INDENT = "    "

TOOLS_ENV = {"EXPAND_ENV_VARS": True, "XONSH_ENCODING_ERRORS": "strict"}
ENCODE_ENV_ONLY = {"XONSH_ENCODING_ERRORS": "strict"}
PATHEXT_ENV = {"PATHEXT": [".COM", ".EXE", ".BAT"]}


def test_subproc_toks_x():
    exp = "![x]"
    obs = subproc_toks("x", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_l():
    exp = "![ls -l]"
    obs = subproc_toks("ls -l", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_git():
    s = 'git commit -am "hello doc"'
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_git_semi():
    s = 'git commit -am "hello doc"'
    exp = "![{0}];".format(s)
    obs = subproc_toks(s + ";", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_git_nl():
    s = 'git commit -am "hello doc"'
    exp = "![{0}]\n".format(s)
    obs = subproc_toks(s + "\n", lexer=LEXER, returnline=True)
    assert exp == obs


def test_bash_macro():
    s = "bash -c ! export var=42; echo $var"
    exp = "![{0}]\n".format(s)
    obs = subproc_toks(s + "\n", lexer=LEXER, returnline=True)
    assert exp == obs


def test_python_macro():
    s = 'python -c ! import os; print(os.path.abspath("/"))'
    exp = "![{0}]\n".format(s)
    obs = subproc_toks(s + "\n", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls():
    s = "ls -l"
    exp = INDENT + "![{0}]".format(s)
    obs = subproc_toks(INDENT + s, mincol=len(INDENT), lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_nl():
    s = "ls -l"
    exp = INDENT + "![{0}]\n".format(s)
    obs = subproc_toks(
        INDENT + s + "\n", mincol=len(INDENT), lexer=LEXER, returnline=True
    )
    assert exp == obs


def test_subproc_toks_indent_ls_no_min():
    s = "ls -l"
    exp = INDENT + "![{0}]".format(s)
    obs = subproc_toks(INDENT + s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_no_min_nl():
    s = "ls -l"
    exp = INDENT + "![{0}]\n".format(s)
    obs = subproc_toks(INDENT + s + "\n", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_no_min_semi():
    s = "ls"
    exp = INDENT + "![{0}];".format(s)
    obs = subproc_toks(INDENT + s + ";", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_no_min_semi_nl():
    s = "ls"
    exp = INDENT + "![{0}];\n".format(s)
    obs = subproc_toks(INDENT + s + ";\n", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_comment():
    s = "ls -l"
    com = "  # lets list"
    exp = "![{0}]{1}".format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_42_comment():
    s = "ls 42"
    com = "  # lets list"
    exp = "![{0}]{1}".format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_str_comment():
    s = 'ls "wakka"'
    com = "  # lets list"
    exp = "![{0}]{1}".format(s, com)
    obs = subproc_toks(s + com, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_comment():
    ind = "    "
    s = "ls -l"
    com = "  # lets list"
    exp = "{0}![{1}]{2}".format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_indent_ls_str():
    ind = "    "
    s = 'ls "wakka"'
    com = "  # lets list"
    exp = "{0}![{1}]{2}".format(ind, s, com)
    obs = subproc_toks(ind + s + com, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_l_semi_ls_first():
    lsdl = "ls -l"
    ls = "ls"
    s = "{0}; {1}".format(lsdl, ls)
    exp = "![{0}]; {1}".format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, maxcol=6, returnline=True)
    assert exp == obs


def test_subproc_toks_ls_l_semi_ls_second():
    lsdl = "ls -l"
    ls = "ls"
    s = "{0}; {1}".format(lsdl, ls)
    exp = "{0}; ![{1}]".format(lsdl, ls)
    obs = subproc_toks(s, lexer=LEXER, mincol=7, returnline=True)
    assert exp == obs


def test_subproc_toks_hello_mom_first():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = "{0}; {1}".format(fst, sec)
    exp = "![{0}]; {1}".format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, maxcol=len(fst) + 1, returnline=True)
    assert exp == obs


def test_subproc_toks_hello_mom_second():
    fst = "echo 'hello'"
    sec = "echo 'mom'"
    s = "{0}; {1}".format(fst, sec)
    exp = "{0}; ![{1}]".format(fst, sec)
    obs = subproc_toks(s, lexer=LEXER, mincol=len(fst), returnline=True)
    assert exp == obs


def test_subproc_toks_hello_bad_leading_single_quotes():
    obs = subproc_toks('echo "hello', lexer=LEXER, returnline=True)
    assert obs is None


def test_subproc_toks_hello_bad_trailing_single_quotes():
    obs = subproc_toks('echo hello"', lexer=LEXER, returnline=True)
    assert obs is None


def test_subproc_toks_hello_bad_leading_triple_quotes():
    obs = subproc_toks('echo """hello', lexer=LEXER, returnline=True)
    assert obs is None


def test_subproc_toks_hello_bad_trailing_triple_quotes():
    obs = subproc_toks('echo hello"""', lexer=LEXER, returnline=True)
    assert obs is None


def test_subproc_toks_hello_mom_triple_quotes_nl():
    s = 'echo """hello\nmom"""'
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_comment():
    exp = None
    obs = subproc_toks("# I am a comment", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_not():
    exp = "not ![echo mom]"
    obs = subproc_toks("not echo mom", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_paren():
    exp = "(![echo mom])"
    obs = subproc_toks("(echo mom)", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_paren_ws():
    exp = "(![echo mom])  "
    obs = subproc_toks("(echo mom)  ", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_not_paren():
    exp = "not (![echo mom])"
    obs = subproc_toks("not (echo mom)", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_and_paren():
    exp = "True and (![echo mom])"
    obs = subproc_toks("True and (echo mom)", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_paren_and_paren():
    exp = "(![echo a]) and (echo b)"
    obs = subproc_toks("(echo a) and (echo b)", maxcol=9, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_semicolon_only():
    exp = None
    obs = subproc_toks(";", lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval():
    s = "echo @(1+1)"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval_multiline_string():
    s = 'echo @("""hello\nmom""")'
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_twopyeval():
    s = "echo @(1+1) @(40 + 2)"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval_parens():
    s = "echo @(1+1)"
    inp = "({0})".format(s)
    exp = "(![{0}])".format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_twopyeval_parens():
    s = "echo @(1+1) @(40+2)"
    inp = "({0})".format(s)
    exp = "(![{0}])".format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval_nested():
    s = "echo @(min(1, 42))"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


@pytest.mark.parametrize(
    "phrase",
    [
        "xandy",
        "xory",
        "xand",
        "andy",
        "xor",
        "ory",
        "x-and",
        "x-or",
        "and-y",
        "or-y",
        "x-and-y",
        "x-or-y",
        "in/and/path",
        "in/or/path",
    ],
)
def test_subproc_toks_and_or(phrase):
    s = "echo " + phrase
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval_nested_parens():
    s = "echo @(min(1, 42))"
    inp = "({0})".format(s)
    exp = "(![{0}])".format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_capstdout():
    s = "echo $(echo bat)"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_capproc():
    s = "echo !(echo bat)"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_pyeval_redirect():
    s = 'echo @("foo") > bar'
    inp = "{0}".format(s)
    exp = "![{0}]".format(s)
    obs = subproc_toks(inp, lexer=LEXER, returnline=True)
    assert exp == obs


def test_subproc_toks_greedy_parens():
    s = "(sort)"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True, greedy=True)
    assert exp == obs


def test_subproc_toks_greedy_parens_inp():
    s = "(sort) < input.txt"
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True, greedy=True)
    assert exp == obs


def test_subproc_toks_greedy_parens_statements():
    s = '(echo "abc"; sleep 1; echo "def")'
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True, greedy=True)
    assert exp == obs


def test_subproc_toks_greedy_parens_statements_with_grep():
    s = '(echo "abc"; sleep 1; echo "def") | grep'
    exp = "![{0}]".format(s)
    obs = subproc_toks(s, lexer=LEXER, returnline=True, greedy=True)
    assert exp == obs


LOGICAL_LINE_CASES = [
    ("""x = 14 + 2""", 0, "x = 14 + 2", 1),
    (
        """x = \\
14 \\
+ 2
""",
        0,
        "x = 14 + 2",
        3,
    ),
    (
        """y = 16
14 \\
+ 2
""",
        1,
        "14 + 2",
        2,
    ),
    (
        '''x = """wow
mom"""
''',
        0,
        'x = """wow\nmom"""',
        2,
    ),
    # test from start
    (
        "echo --option1 value1 \\\n"
        "     --option2 value2 \\\n"
        "     --optionZ valueZ",
        0,
        "echo --option1 value1      --option2 value2      --optionZ valueZ",
        3,
    ),
    # test from second line
    (
        "echo --option1 value1 \\\n"
        "     --option2 value2 \\\n"
        "     --optionZ valueZ",
        1,
        "echo --option1 value1      --option2 value2      --optionZ valueZ",
        3,
    ),
    ('"""\n', 0, '"""', 1),
]


@pytest.mark.parametrize("src, idx, exp_line, exp_n", LOGICAL_LINE_CASES)
def test_get_logical_line(src, idx, exp_line, exp_n):
    lines = src.splitlines()
    line, n, start = get_logical_line(lines, idx)
    assert exp_line == line
    assert exp_n == n


@pytest.mark.parametrize("src, idx, exp_line, exp_n", LOGICAL_LINE_CASES)
def test_replace_logical_line(src, idx, exp_line, exp_n):
    lines = src.splitlines()
    logical = exp_line
    while idx > 0 and lines[idx - 1].endswith("\\"):
        idx -= 1
    replace_logical_line(lines, logical, idx, exp_n)
    exp = src.replace("\\\n", "").strip()
    lc = get_line_continuation() + "\n"
    obs = "\n".join(lines).replace(lc, "").strip()
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("f(1,10),x.y", True),
        ('"x"', True),
        ("'y'", True),
        ('b"x"', True),
        ("r'y'", True),
        ("f'z'", True),
        ('"""hello\nmom"""', True),
    ],
)
def test_check_quotes(inp, exp):
    obs = check_quotes(inp)
    assert exp is obs


@pytest.mark.parametrize("inp", ["f(1,10),x.y"])
def test_is_balanced_parens(inp):
    obs = is_balanced(inp, "(", ")")
    assert obs


@pytest.mark.parametrize("inp", ["f(x.", "f(1,x." "f((1,10),x.y"])
def test_is_not_balanced_parens(inp):
    obs = is_balanced(inp, "(", ")")
    assert not obs


@pytest.mark.parametrize(
    "inp, exp", [("f(x.", "x."), ("f(1,x.", "x."), ("f((1,10),x.y", "x.y")]
)
def test_subexpr_from_unbalanced_parens(inp, exp):
    obs = subexpr_from_unbalanced(inp, "(", ")")
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("f(x.", "f"),
        ("f(1,x.", "f"),
        ("f((1,10),x.y", "f"),
        ("wakka().f((1,10),x.y", ".f"),
        ("wakka(f((1,10),x.y", "f"),
        ("wakka(jawakka().f((1,10),x.y", ".f"),
        ("wakka(jawakka().f((1,10),x.y)", "wakka"),
    ],
)
def test_subexpr_before_unbalanced_parens(inp, exp):
    obs = subexpr_before_unbalanced(inp, "(", ")")
    assert exp == obs


@pytest.mark.parametrize(
    "line, exp",
    [
        ("", True),
        ("wakka jawaka", True),
        ("rm *; echo hello world", True),
        ("()", True),
        ("f()", True),
        ("echo * yo ; echo eggs", True),
        ("(", False),
        (")", False),
        ("(cmd;", False),
        ("cmd;)", False),
    ],
)
def test_balanced_parens(line, exp):
    obs = balanced_parens(line, lexer=LEXER)
    if exp:
        assert obs
    else:
        assert not obs


@pytest.mark.parametrize(
    "line, mincol, exp",
    [
        ("ls && echo a", 0, 4),
        ("ls && echo a", 6, None),
        ("ls && echo a || echo b", 6, 14),
        ("(ls) && echo a", 1, 4),
        ("not ls && echo a", 0, 8),
        ("not (ls) && echo a", 0, 8),
        ("bash -c ! export var=42; echo $var", 0, 35),
        ('python -c ! import os; print(os.path.abspath("/"))', 0, 51),
        ("echo * yo ; echo eggs", 0, 11),
    ],
)
def test_find_next_break(line, mincol, exp):
    obs = find_next_break(line, mincol=mincol, lexer=LEXER)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (42, True),
        (42.0, False),
        ("42", False),
        ("42.0", False),
        ([42], False),
        ([], False),
        (None, False),
        ("", False),
    ],
)
def test_is_int(inp, exp):
    obs = is_int(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (42.0, True),
        (42.000101010010101010101001010101010001011100001101101011100, True),
        (42, False),
        ("42", False),
        ("42.0", False),
        ([42], False),
        ([], False),
        (None, False),
        ("", False),
        (False, False),
        (True, False),
    ],
)
def test_is_float(inp, exp):
    obs = is_float(inp)
    assert exp == obs


def test_is_string_true():
    assert is_string("42.0")


def test_is_string_false():
    assert not is_string(42.0)


def test_is_callable_true():
    assert is_callable(lambda: 42.0)


def test_is_callable_false():
    assert not is_callable(42.0)


@pytest.mark.parametrize("inp", ["42.0", lambda: 42.0])
def test_is_string_or_callable_true(inp):
    assert is_string_or_callable(inp)


def test_is_string_or_callable_false():
    assert not is_string(42.0)


@pytest.mark.parametrize("inp", [42, "42"])
def test_always_true(inp):
    assert always_true(inp)


@pytest.mark.parametrize("inp", [42, "42"])
def test_always_false(inp):
    assert not always_false(inp)


@pytest.mark.parametrize("inp, exp", [(42, "42"), ("42", "42")])
def test_ensure_string(inp, exp):
    obs = ensure_string(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("", set()),
        ("a", {"a"}),
        (os.pathsep.join(["a", "b"]), {"a", "b"}),
        (os.pathsep.join(["a", "b", "c"]), {"a", "b", "c"}),
    ],
)
def test_pathsep_to_set(inp, exp):
    obs = pathsep_to_set(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (set(), ""),
        ({"a"}, "a"),
        ({"a", "b"}, os.pathsep.join(["a", "b"])),
        ({"a", "b", "c"}, os.pathsep.join(["a", "b", "c"])),
    ],
)
def test_set_to_pathsep(inp, exp):
    obs = set_to_pathsep(inp, sort=(len(inp) > 1))
    assert exp == obs


@pytest.mark.parametrize("inp", ["42.0", ["42.0"]])
def test_is_string_seq_true(inp):
    assert is_string_seq(inp)


def test_is_string_seq_false():
    assert not is_string_seq([42.0])


def test_is_nonstring_seq_of_strings_true():
    assert is_nonstring_seq_of_strings(["42.0"])


def test_is_nonstring_seq_of_strings_false():
    assert not is_nonstring_seq_of_strings([42.0])


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("", []),
        ("a", ["a"]),
        (os.pathsep.join(["a", "b"]), ["a", "b"]),
        (os.pathsep.join(["a", "b", "c"]), ["a", "b", "c"]),
    ],
)
def test_pathsep_to_seq(inp, exp):
    obs = pathsep_to_seq(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ([], ""),
        (["a"], "a"),
        (["a", "b"], os.pathsep.join(["a", "b"])),
        (["a", "b", "c"], os.pathsep.join(["a", "b", "c"])),
    ],
)
def test_seq_to_pathsep(inp, exp):
    obs = seq_to_pathsep(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("", []),
        ("a", ["A"]),
        (os.pathsep.join(["a", "B"]), ["A", "B"]),
        (os.pathsep.join(["A", "b", "c"]), ["A", "B", "C"]),
    ],
)
def test_pathsep_to_upper_seq(inp, exp):
    obs = pathsep_to_upper_seq(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ([], ""),
        (["a"], "A"),
        (["a", "b"], os.pathsep.join(["A", "B"])),
        (["a", "B", "c"], os.pathsep.join(["A", "B", "C"])),
    ],
)
def test_seq_to_upper_pathsep(inp, exp):
    obs = seq_to_upper_pathsep(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("/home/wakka", False),
        (["/home/jawaka"], False),
        (EnvPath(["/home/jawaka"]), True),
        (EnvPath(["jawaka"]), True),
        (EnvPath(b"jawaka:wakka"), True),
    ],
)
def test_is_env_path(inp, exp):
    obs = is_env_path(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("/home/wakka", ["/home/wakka"]),
        ("/home/wakka" + os.pathsep + "/home/jawaka", ["/home/wakka", "/home/jawaka"]),
        (b"/home/wakka", ["/home/wakka"]),
    ],
)
def test_str_to_env_path(inp, exp):
    obs = str_to_env_path(inp)
    assert exp == obs.paths


@pytest.mark.parametrize(
    "inp, exp",
    [
        (["/home/wakka"], "/home/wakka"),
        (["/home/wakka", "/home/jawaka"], "/home/wakka" + os.pathsep + "/home/jawaka"),
    ],
)
def test_env_path_to_str(inp, exp):
    obs = env_path_to_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "left, right, exp",
    [
        (
            EnvPath(["/home/wakka"]),
            ["/home/jawaka"],
            EnvPath(["/home/wakka", "/home/jawaka"]),
        ),
        (["a"], EnvPath(["b"]), EnvPath(["a", "b"])),
        (EnvPath(["c"]), EnvPath(["d"]), EnvPath(["c", "d"])),
    ],
)
def test_env_path_add(left, right, exp):
    obs = left + right
    assert is_env_path(obs)
    assert exp == obs


# helper
def expand(path):
    return os.path.expanduser(os.path.expandvars(path))


@pytest.mark.parametrize("env", [TOOLS_ENV, ENCODE_ENV_ONLY])
@pytest.mark.parametrize(
    "inp, exp",
    [
        ("xonsh_dir", "xonsh_dir"),
        (".", "."),
        ("../", "../"),
        ("~/", "~/"),
        (b"~/../", "~/../"),
    ],
)
def test_env_path_getitem(inp, exp, xonsh_builtins, env):
    xonsh_builtins.__xonsh__.env = env
    obs = EnvPath(inp)[0]  # call to __getitem__
    if env.get("EXPAND_ENV_VARS"):
        assert expand(exp) == obs
    else:
        assert exp == obs


@pytest.mark.parametrize("env", [TOOLS_ENV, ENCODE_ENV_ONLY])
@pytest.mark.parametrize(
    "inp, exp",
    [
        (
            os.pathsep.join(["xonsh_dir", "../", ".", "~/"]),
            ["xonsh_dir", "../", ".", "~/"],
        ),
        (
            "/home/wakka" + os.pathsep + "/home/jakka" + os.pathsep + "~/",
            ["/home/wakka", "/home/jakka", "~/"],
        ),
    ],
)
def test_env_path_multipath(inp, exp, xonsh_builtins, env):
    # cases that involve path-separated strings
    xonsh_builtins.__xonsh__.env = env
    if env == TOOLS_ENV:
        obs = [i for i in EnvPath(inp)]
        assert [expand(i) for i in exp] == obs
    else:
        obs = [i for i in EnvPath(inp)]
        assert [i for i in exp] == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (pathlib.Path("/home/wakka"), ["/home/wakka".replace("/", os.sep)]),
        (pathlib.Path("~/"), ["~"]),
        (pathlib.Path("."), ["."]),
        (
            ["/home/wakka", pathlib.Path("/home/jakka"), "~/"],
            ["/home/wakka", "/home/jakka".replace("/", os.sep), "~/"],
        ),
        (["/home/wakka", pathlib.Path("../"), "../"], ["/home/wakka", "..", "../"]),
        (["/home/wakka", pathlib.Path("~/"), "~/"], ["/home/wakka", "~", "~/"]),
    ],
)
def test_env_path_with_pathlib_path_objects(inp, exp, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = TOOLS_ENV
    # iterate over EnvPath to acquire all expanded paths
    obs = [i for i in EnvPath(inp)]
    assert [expand(i) for i in exp] == obs


@pytest.mark.parametrize("inp", ["42.0", [42.0]])
def test_is_nonstring_seq_of_strings_false(inp):
    assert not is_nonstring_seq_of_strings(inp)


# helper
def mkpath(*paths):
    """Build os-dependent paths properly."""
    return os.sep + os.sep.join(paths)


@pytest.mark.parametrize(
    "inp, exp",
    [
        (
            [mkpath("home", "wakka"), mkpath("home", "jakka"), mkpath("home", "yakka")],
            [mkpath("home", "wakka"), mkpath("home", "jakka")],
        )
    ],
)
def test_env_path_slice_get_all_except_last_element(inp, exp):
    obs = EnvPath(inp)[:-1]
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (
            [mkpath("home", "wakka"), mkpath("home", "jakka"), mkpath("home", "yakka")],
            [mkpath("home", "jakka"), mkpath("home", "yakka")],
        )
    ],
)
def test_env_path_slice_get_all_except_first_element(inp, exp):
    obs = EnvPath(inp)[1:]
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp_a, exp_b",
    [
        (
            [
                mkpath("home", "wakka"),
                mkpath("home", "jakka"),
                mkpath("home", "yakka"),
                mkpath("home", "takka"),
            ],
            [mkpath("home", "wakka"), mkpath("home", "yakka")],
            [mkpath("home", "jakka"), mkpath("home", "takka")],
        )
    ],
)
def test_env_path_slice_path_with_step(inp, exp_a, exp_b):
    obs_a = EnvPath(inp)[0::2]
    assert exp_a == obs_a
    obs_b = EnvPath(inp)[1::2]
    assert exp_b == obs_b


@pytest.mark.parametrize(
    "inp, exp",
    [
        (
            [
                mkpath("home", "wakka"),
                mkpath("home", "xakka"),
                mkpath("other", "zakka"),
                mkpath("another", "akka"),
                mkpath("home", "bakka"),
            ],
            [mkpath("other", "zakka"), mkpath("another", "akka")],
        )
    ],
)
def test_env_path_keep_only_non_home_paths(inp, exp):
    obs = EnvPath(inp)[2:4]
    assert exp == obs


@pytest.mark.parametrize("inp", [True, False])
def test_is_bool_true(inp):
    assert True == is_bool(inp)


@pytest.mark.parametrize("inp", [1, "yooo hooo!"])
def test_is_bool_false(inp):
    assert False == is_bool(inp)


@pytest.mark.parametrize(
    "inp, exp",
    [
        (True, True),
        (False, False),
        (None, False),
        ("", False),
        ("0", False),
        ("False", False),
        ("NONE", False),
        ("TRUE", True),
        ("1", True),
        (0, False),
        (1, True),
    ],
)
def test_to_bool(inp, exp):
    obs = to_bool(inp)
    assert exp == obs


@pytest.mark.parametrize("inp, exp", [(True, "1"), (False, "")])
def test_bool_to_str(inp, exp):
    assert bool_to_str(inp) == exp


@pytest.mark.parametrize(
    "inp, exp",
    [(True, True), (False, True), (1, True), (0, True), ("Yolo", False), (1.0, False)],
)
def test_is_bool_or_int(inp, exp):
    obs = is_bool_or_int(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (True, True),
        (False, False),
        (1, 1),
        (0, 0),
        ("", False),
        (0.0, False),
        (1.0, True),
        ("T", True),
        ("f", False),
        ("0", 0),
        ("10", 10),
    ],
)
def test_to_bool_or_int(inp, exp):
    obs = to_bool_or_int(inp)
    assert exp == obs


@pytest.mark.parametrize("inp, exp", [(True, "1"), (False, ""), (1, "1"), (0, "0")])
def test_bool_or_int_to_str(inp, exp):
    obs = bool_or_int_to_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (42, slice(42, 43)),
        (0, slice(0, 1)),
        (None, slice(None, None, None)),
        (slice(1, 2), slice(1, 2)),
        ("-1", slice(-1, None, None)),
        ("42", slice(42, 43)),
        ("-42", slice(-42, -41)),
        ("1:2:3", slice(1, 2, 3)),
        ("1::3", slice(1, None, 3)),
        (":", slice(None, None, None)),
        ("1:", slice(1, None, None)),
        ("[1:2:3]", slice(1, 2, 3)),
        ("(1:2:3)", slice(1, 2, 3)),
        ((4, 8, 10), slice(4, 8, 10)),
        ([10, 20], slice(10, 20)),
    ],
)
def test_ensure_slice(inp, exp):
    obs = ensure_slice(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ((range(50), slice(25, 40)), list(i for i in range(25, 40))),
        (
            ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [slice(1, 4), slice(6, None)]),
            [2, 3, 4, 7, 8, 9, 10],
        ),
        (([1, 2, 3, 4, 5], [slice(-2, None), slice(-5, -3)]), [4, 5, 1, 2]),
    ],
)
def test_get_portions(inp, exp):
    obs = get_portions(*inp)
    assert list(obs) == exp


@pytest.mark.parametrize(
    "inp",
    [
        "42.3",
        "3:asd5:1",
        "test",
        "6.53:100:5",
        "4:-",
        "2:15-:3",
        "50:-:666",
        object(),
        [1, 5, 3, 4],
        ("foo"),
    ],
)
def test_ensure_slice_invalid(inp):
    with pytest.raises(ValueError):
        obs = ensure_slice(inp)


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("42", True),
        ("42.0", False),
        (42, False),
        ([42], False),
        ([], False),
        (None, False),
        ("", False),
        (False, False),
        (True, False),
    ],
)
def test_is_int_as_str(inp, exp):
    obs = is_int_as_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("20", False),
        ("20%", False),
        ((20, "c"), False),
        ((20.0, "m"), False),
        ((20.0, "c"), True),
        ((20.0, "%"), True),
    ],
)
def test_is_dynamic_cwd_width(inp, exp):
    obs = is_dynamic_cwd_width(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (42, False),
        (None, False),
        ("42", False),
        ("-42", False),
        (slice(1, 2, 3), False),
        ([], False),
        (False, False),
        (True, False),
        ("1:2:3", True),
        ("1::3", True),
        ("1:", True),
        (":", True),
        ("[1:2:3]", True),
        ("(1:2:3)", True),
        ("r", False),
        ("r:11", False),
    ],
)
def test_is_slice_as_str(inp, exp):
    obs = is_slice_as_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("throwback.log", True),
        ("", True),
        (None, True),
        (True, False),
        (False, False),
        (42, False),
        ([1, 2, 3], False),
        ((1, 2), False),
        (("wrong", "parameter"), False),
        pytest.param("/dev/null", True, marks=skip_if_on_windows),
    ],
)
def test_is_logfile_opt(inp, exp):
    obs = is_logfile_opt(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (True, None),
        (False, None),
        (1, None),
        (None, None),
        ("throwback.log", "throwback.log"),
        pytest.param("/dev/null", "/dev/null", marks=skip_if_on_windows),
        pytest.param(
            "/dev/nonexistent_dev",
            "/dev/nonexistent_dev"
            if is_writable_file("/dev/nonexistent_dev")
            else None,
            marks=skip_if_on_windows,
        ),
    ],
)
def test_to_logfile_opt(inp, exp):
    obs = to_logfile_opt(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        (None, ""),
        ("", ""),
        ("throwback.log", "throwback.log"),
        ("/dev/null", "/dev/null"),
    ],
)
def test_logfile_opt_to_str(inp, exp):
    obs = logfile_opt_to_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("20", (20.0, "c")),
        ("20%", (20.0, "%")),
        ((20, "c"), (20.0, "c")),
        ((20, "%"), (20.0, "%")),
        ((20.0, "c"), (20.0, "c")),
        ((20.0, "%"), (20.0, "%")),
        ("inf", (float("inf"), "c")),
    ],
)
def test_to_dynamic_cwd_tuple(inp, exp):
    obs = to_dynamic_cwd_tuple(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [((20.0, "c"), "20.0"), ((20.0, "%"), "20.0%"), ((float("inf"), "c"), "inf")],
)
def test_dynamic_cwd_tuple_to_str(inp, exp):
    obs = dynamic_cwd_tuple_to_str(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "st, esc",
    [
        ("", ""),
        ("foo", "foo"),
        ("foo&bar", "foo^&bar"),
        ('foo$?-/_"\\', 'foo$?-/_^"\\'),
        ("^&<>|", "^^^&^<^>^|"),
        ("()<>", "^(^)^<^>"),
    ],
)
def test_escape_windows_cmd_string(st, esc):
    obs = escape_windows_cmd_string(st)
    assert esc == obs


@pytest.mark.parametrize(
    "st, esc, forced",
    [
        ("", '""', None),
        ("foo", "foo", '"foo"'),
        (
            r'arg1 "hallo, "world""  "\some\path with\spaces")',
            r'"arg1 \"hallo, \"world\"\"  \"\some\path with\spaces\")"',
            None,
        ),
        (
            r'"argument"2" argument3 argument4',
            r'"\"argument\"2\" argument3 argument4"',
            None,
        ),
        (r'"\foo\bar bar\foo\" arg', r'"\"\foo\bar bar\foo\\\" arg"', None),
        (
            r"\\machine\dir\file.bat",
            r"\\machine\dir\file.bat",
            r'"\\machine\dir\file.bat"',
        ),
        (
            r'"\\machine\dir space\file.bat"',
            r'"\"\\machine\dir space\file.bat\""',
            None,
        ),
    ],
)
def test_argvquote(st, esc, forced):
    obs = argvquote(st)
    assert esc == obs

    if forced is None:
        forced = esc
    obs = argvquote(st, force=True)
    assert forced == obs


@pytest.mark.parametrize("inp", ["no string here", ""])
def test_partial_string_none(inp):
    assert check_for_partial_string(inp) == (None, None, None)


@pytest.mark.parametrize(
    "leaders", [(("", 0), ("not empty", 9)), (("not empty", 9), ("", 0))]
)
@pytest.mark.parametrize("prefix", ["b", "rb", "r"])
@pytest.mark.parametrize("quote", ['"', '"""'])
def test_partial_string(leaders, prefix, quote):
    (l, l_len), (f, f_len) = leaders
    s = prefix + quote
    t = s + "test string" + quote
    t_len = len(t)
    # single string
    test_string = l + t + f
    obs = check_for_partial_string(test_string)
    exp = l_len, l_len + t_len, s
    assert obs == exp
    # single partial
    test_string = l + f + s + "test string"
    obs = check_for_partial_string(test_string)
    exp = l_len + f_len, None, s
    assert obs == exp
    # two strings
    test_string = l + t + f + l + t + f
    obs = check_for_partial_string(test_string)
    exp = (l_len + t_len + f_len + l_len), (l_len + t_len + f_len + l_len + t_len), s
    assert obs == exp
    # one string, one partial
    test_string = l + t + f + l + s + "test string"
    obs = check_for_partial_string(test_string)
    exp = l_len + t_len + f_len + l_len, None, s
    assert obs == exp


def test_executables_in(xonsh_builtins):
    expected = set()
    types = ("file", "directory", "brokensymlink")
    if ON_WINDOWS:
        # Don't test symlinks on windows since it requires admin
        types = ("file", "directory")
    executables = (True, False)
    with TemporaryDirectory() as test_path:
        for _type in types:
            for executable in executables:
                fname = "%s_%s" % (_type, executable)
                if _type == "none":
                    continue
                if _type == "file" and executable:
                    ext = ".exe" if ON_WINDOWS else ""
                    expected.add(fname + ext)
                else:
                    ext = ""
                path = os.path.join(test_path, fname + ext)
                if _type == "file":
                    with open(path, "w") as f:
                        f.write(fname)
                elif _type == "directory":
                    os.mkdir(path)
                elif _type == "brokensymlink":
                    tmp_path = os.path.join(test_path, "i_wont_exist")
                    with open(tmp_path, "w") as f:
                        f.write("deleteme")
                        os.symlink(tmp_path, path)
                    os.remove(tmp_path)
                if executable and not _type == "brokensymlink":
                    os.chmod(path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
            if ON_WINDOWS:
                xonsh_builtins.__xonsh__.env = PATHEXT_ENV
                result = set(executables_in(test_path))
            else:
                result = set(executables_in(test_path))
    assert expected == result


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("yo", "[Yy][Oo]"),
        ("[a-f]123e", "[a-f]123[Ee]"),
        ("${HOME}/yo", "${HOME}/[Yy][Oo]"),
        ("./yo/mom", "./[Yy][Oo]/[Mm][Oo][Mm]"),
        ("Eßen", "[Ee][Ss]?[Ssß][Ee][Nn]"),
    ],
)
def test_expand_case_matching(inp, exp):
    obs = expand_case_matching(inp)
    assert exp == obs


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("foo", "foo"),
        ("$foo $bar", "bar $bar"),
        ("$foobar", "$foobar"),
        ("$foo $spam", "bar eggs"),
        ("$an_int$spam$a_bool", "42eggsTrue"),
        ("bar$foo$spam$foo $an_int $none", "barbareggsbar 42 None"),
        ("$foo/bar", "bar/bar"),
        ("${'foo'} $spam", "bar eggs"),
        ("${'foo'} ${'a_bool'}", "bar True"),
        ("${'foo'}bar", "barbar"),
        ("${'foo'}/bar", "bar/bar"),
        ("${\"foo'}", "${\"foo'}"),
        ("$?bar", "$?bar"),
        ("$foo}bar", "bar}bar"),
        ("${'foo", "${'foo"),
        (b"foo", "foo"),
        (b"$foo bar", "bar bar"),
        (b"${'foo'}bar", "barbar"),
    ],
)
def test_expandvars(inp, exp, xonsh_builtins):
    """Tweaked for xonsh cases from CPython `test_genericpath.py`"""
    env = Env(
        {"foo": "bar", "spam": "eggs", "a_bool": True, "an_int": 42, "none": None}
    )
    xonsh_builtins.__xonsh__.env = env
    assert expandvars(inp) == exp


@pytest.mark.parametrize(
    "inp, fmt, exp",
    [
        (572392800.0, None, 572392800.0),
        ("42.1459", None, 42.1459),
        (
            dt.datetime(2016, 8, 2, 13, 24),
            None,
            dt.datetime(2016, 8, 2, 13, 24).timestamp(),
        ),
        ("2016-8-10 16:14", None, dt.datetime(2016, 8, 10, 16, 14).timestamp()),
        (
            "2016/8/10 16:14:40",
            "%Y/%m/%d %H:%M:%S",
            dt.datetime(2016, 8, 10, 16, 14, 40).timestamp(),
        ),
    ],
)
def test_ensure_timestamp(inp, fmt, exp, xonsh_builtins):
    xonsh_builtins.__xonsh__.env["XONSH_DATETIME_FORMAT"] = "%Y-%m-%d %H:%M"
    obs = ensure_timestamp(inp, fmt)
    assert exp == obs


@pytest.mark.parametrize("expand_user", [True, False])
@pytest.mark.parametrize(
    "inp, expand_env_vars, exp_end",
    [
        ("~/test.txt", True, "/test.txt"),
        ("~/$foo", True, "/bar"),
        ("~/test/$a_bool", True, "/test/True"),
        ("~/test/$an_int", True, "/test/42"),
        ("~/test/$none", True, "/test/None"),
        ("~/$foo", False, "/$foo"),
    ],
)
def test_expand_path(expand_user, inp, expand_env_vars, exp_end, xonsh_builtins):
    if os.sep != "/":
        inp = inp.replace("/", os.sep)
        exp_end = exp_end.replace("/", os.sep)

    env = Env({"foo": "bar", "a_bool": True, "an_int": 42, "none": None})
    env["EXPAND_ENV_VARS"] = expand_env_vars
    xonsh_builtins.__xonsh__.env = env

    path = expand_path(inp, expand_user=expand_user)

    if expand_user:
        home_path = os.path.expanduser("~")
        assert path == home_path + exp_end
    else:
        assert path == "~" + exp_end


def test_swap_values():
    orig = {"x": 1}
    updates = {"x": 42, "y": 43}
    with swap_values(orig, updates):
        assert orig["x"] == 42
        assert orig["y"] == 43
    assert orig["x"] == 1
    assert "y" not in orig


@pytest.mark.parametrize(
    "arguments, expected_docstring",
    [
        (
            {"deprecated_in": "0.5.10", "removed_in": "0.6.0"},
            "my_function has been deprecated in version 0.5.10 and will be removed "
            "in version 0.6.0",
        ),
        (
            {"deprecated_in": "0.5.10"},
            "my_function has been deprecated in version 0.5.10",
        ),
        (
            {"removed_in": "0.6.0"},
            "my_function has been deprecated and will be removed in version 0.6.0",
        ),
        ({}, "my_function has been deprecated"),
    ],
)
def test_deprecated_docstrings_with_empty_docstring(arguments, expected_docstring):
    @deprecated(**arguments)
    def my_function():
        pass

    assert my_function.__doc__ == expected_docstring


@pytest.mark.parametrize(
    "arguments, expected_docstring",
    [
        (
            {"deprecated_in": "0.5.10", "removed_in": "0.6.0"},
            "Does nothing.\n\nmy_function has been deprecated in version 0.5.10 and "
            "will be removed in version 0.6.0",
        ),
        (
            {"deprecated_in": "0.5.10"},
            "Does nothing.\n\nmy_function has been deprecated in version 0.5.10",
        ),
        (
            {"removed_in": "0.6.0"},
            "Does nothing.\n\nmy_function has been deprecated and will be removed "
            "in version 0.6.0",
        ),
        ({}, "Does nothing.\n\nmy_function has been deprecated"),
    ],
)
def test_deprecated_docstrings_with_nonempty_docstring(arguments, expected_docstring):
    @deprecated(**arguments)
    def my_function():
        """Does nothing."""
        pass

    assert my_function.__doc__ == expected_docstring


def test_deprecated_warning_raised():
    @deprecated()
    def my_function():
        pass

    with warnings.catch_warnings(record=True) as warning:
        warnings.simplefilter("always")

        my_function()

        assert issubclass(warning.pop().category, DeprecationWarning)


def test_deprecated_warning_contains_message():
    @deprecated()
    def my_function():
        pass

    with warnings.catch_warnings(record=True) as warning:
        warnings.simplefilter("always")

        my_function()

        assert str(warning.pop().message) == "my_function has been deprecated"


@pytest.mark.parametrize("expired_version", ["0.1.0", __version__])
def test_deprecated_past_expiry_raises_assertion_error(expired_version):
    @deprecated(removed_in=expired_version)
    def my_function():
        pass

    with pytest.raises(AssertionError):
        my_function()


@skip_if_on_windows
def test_iglobpath_no_dotfiles(xonsh_builtins):
    d = os.path.dirname(__file__)
    g = d + "/*"
    files = list(iglobpath(g, include_dotfiles=False))
    assert d + "/.somedotfile" not in files


@skip_if_on_windows
def test_iglobpath_dotfiles(xonsh_builtins):
    d = os.path.dirname(__file__)
    g = d + "/*"
    files = list(iglobpath(g, include_dotfiles=True))
    assert d + "/.somedotfile" in files


@skip_if_on_windows
def test_iglobpath_no_dotfiles_recursive(xonsh_builtins):
    d = os.path.dirname(__file__)
    g = d + "/**"
    files = list(iglobpath(g, include_dotfiles=False))
    assert d + "/bin/.someotherdotfile" not in files


@skip_if_on_windows
def test_iglobpath_dotfiles_recursive(xonsh_builtins):
    d = os.path.dirname(__file__)
    g = d + "/**"
    files = list(iglobpath(g, include_dotfiles=True))
    assert d + "/bin/.someotherdotfile" in files


def test_iglobpath_empty_str(monkeypatch, xonsh_builtins):
    # makes sure that iglobpath works, even when os.scandir() and os.listdir()
    # fail to return valid results, like an empty filename
    def mockscandir(path):
        yield ""

    if hasattr(os, "scandir"):
        monkeypatch.setattr(os, "scandir", mockscandir)

    def mocklistdir(path):
        return [""]

    monkeypatch.setattr(os, "listdir", mocklistdir)
    paths = list(iglobpath("some/path"))
    assert len(paths) == 0


def test_all_permutations():
    obs = {"".join(p) for p in all_permutations("ABC")}
    exp = {
        "A",
        "B",
        "C",
        "AB",
        "AC",
        "BA",
        "BC",
        "CA",
        "CB",
        "ACB",
        "CBA",
        "BAC",
        "CAB",
        "BCA",
        "ABC",
    }
    assert obs == exp
