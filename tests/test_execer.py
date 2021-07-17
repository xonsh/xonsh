# -*- coding: utf-8 -*-
"""Tests the xonsh lexer."""
import os

from tools import (
    check_eval,
    check_exec,
    check_parse,
    skip_if_on_unix,
    skip_if_on_windows,
)

import pytest


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_builtins, xonsh_execer):
    return xonsh_execer


@skip_if_on_unix
def test_win_ipconfig():
    assert check_eval(os.environ["SYSTEMROOT"] + "\\System32\\ipconfig.exe /all")


@skip_if_on_unix
def test_ipconfig():
    assert check_eval("ipconfig /all")


@skip_if_on_windows
def test_bin_ls():
    assert check_eval("/bin/ls -l")


def test_ls_dashl():
    assert check_parse("ls -l")


def test_which_ls():
    assert check_parse("which ls")


def test_echo_hello():
    assert check_parse("echo hello")


def test_echo_star_with_semi():
    assert check_parse("echo * spam ; ![echo eggs]\n")


def test_simple_func():
    code = "def prompt():\n" "    return '{user}'.format(user='me')\n"
    assert check_parse(code)


def test_lookup_alias():
    code = "def foo(a,  s=None):\n" '    return "bar"\n' "@(foo)\n"
    assert check_parse(code)


def test_lookup_anon_alias():
    code = 'echo "hi" | @(lambda a, s=None: a[0]) foo bar baz\n'
    assert check_parse(code)


def test_simple_func_broken():
    code = "def prompt():\n" "    return '{user}'.format(\n" "       user='me')\n"
    assert check_parse(code)


def test_bad_indent():
    code = "if True:\n" "x = 1\n"
    with pytest.raises(SyntaxError):
        check_parse(code)


def test_comment_colon_ending():
    code = "# this is a comment:\necho hello"
    assert check_parse(code)


def test_good_rhs_subproc():
    # nonsense but parsable
    code = "str().split() | ![grep exit]\n"
    assert code


def test_bad_rhs_subproc():
    # nonsense but unparsable
    code = "str().split() | grep exit\n"
    with pytest.raises(SyntaxError):
        check_parse(code)


def test_indent_with_empty_line():
    code = "if True:\n" "\n" "    some_command for_sub_process_mode\n"
    assert check_parse(code)


def test_command_in_func():
    code = "def f():\n" "    echo hello\n"
    assert check_parse(code)


def test_command_in_func_with_comment():
    code = "def f():\n" "    echo hello # comment\n"
    assert check_parse(code)


def test_pyeval_redirect():
    code = 'echo @("foo") > bar\n'
    assert check_parse(code)


def test_pyeval_multiline_str():
    code = 'echo @("""hello\nmom""")\n'
    assert check_parse(code)


def test_echo_comma():
    code = "echo ,\n"
    assert check_parse(code)


def test_echo_comma_val():
    code = "echo ,1\n"
    assert check_parse(code)


def test_echo_comma_2val():
    code = "echo 1,2\n"
    assert check_parse(code)


def test_echo_line_cont():
    code = 'echo "1 \\\n2"\n'
    assert check_parse(code)


@pytest.mark.parametrize(
    "code",
    [
        "echo a and \\\necho b\n",
        "echo a \\\n or echo b\n",
        "echo a \\\n or echo b and \\\n echo c\n",
        "if True:\\\n    echo a \\\n    b\n",
    ],
)
def test_two_echo_line_cont(code):
    assert check_parse(code)


def test_eval_eol():
    assert check_eval("0") and check_eval("0\n")


def test_annotated_assign():
    # issue #3959 - didn't work because of `CtxAwareTransformer`
    assert check_exec("x : int = 42")


def test_exec_eol():
    locs = dict()
    assert check_exec("a=0", locs=locs) and check_exec("a=0\n", locs=locs)


def test_exec_print(capsys):
    ls = {"nested": "some long list"}
    check_exec("print(ls)", locs=dict(ls=ls))
    out, err = capsys.readouterr()
    assert out.strip() == repr(ls)


def test_exec_function_scope():
    # issue 4363
    assert check_exec("x = 0; (lambda: x)()")
    assert check_exec("x = 0; [x for _ in [0]]")


def test_exec_scope_reuse():
    # Scopes should not be reused between execs.
    # A first-pass incorrect solution to issue 4363 made this mistake.
    assert check_exec("x = 0")
    with pytest.raises(NameError):
        check_exec("print(x)")
