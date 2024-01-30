"""Tests the xonsh lexer."""

import os

import pytest

from xonsh.pytest.tools import ON_WINDOWS, skip_if_on_unix, skip_if_on_windows


@pytest.fixture
def check_eval(xonsh_execer, xonsh_session, monkeypatch):
    def factory(input):
        env = {
            "AUTO_CD": False,
            "XONSH_ENCODING": "utf-8",
            "XONSH_ENCODING_ERRORS": "strict",
            "PATH": [],
        }
        for key, val in env.items():
            monkeypatch.setitem(xonsh_session.env, key, val)
        if ON_WINDOWS:
            monkeypatch.setitem(
                xonsh_session.env, "PATHEXT", [".COM", ".EXE", ".BAT", ".CMD"]
            )
        xonsh_execer.eval(input)
        return True

    return factory


@skip_if_on_unix
def test_win_ipconfig(check_eval):
    assert check_eval(os.environ["SYSTEMROOT"] + "\\System32\\ipconfig.exe /all")


@skip_if_on_unix
def test_ipconfig(check_eval):
    assert check_eval("ipconfig /all")


@skip_if_on_windows
def test_bin_ls(check_eval):
    assert check_eval("/bin/ls -l")


def test_ls_dashl(xonsh_execer_parse):
    assert xonsh_execer_parse("ls -l")


def test_which_ls(xonsh_execer_parse):
    assert xonsh_execer_parse("which ls")


def test_echo_hello(xonsh_execer_parse):
    assert xonsh_execer_parse("echo hello")


def test_echo_star_with_semi(xonsh_execer_parse):
    assert xonsh_execer_parse("echo * spam ; ![echo eggs]\n")


def test_simple_func(xonsh_execer_parse):
    code = "def prompt():\n" "    return '{user}'.format(user='me')\n"
    assert xonsh_execer_parse(code)


def test_lookup_alias(xonsh_execer_parse):
    code = "def foo(a,  s=None):\n" '    return "bar"\n' "@(foo)\n"
    assert xonsh_execer_parse(code)


def test_lookup_anon_alias(xonsh_execer_parse):
    code = 'echo "hi" | @(lambda a, s=None: a[0]) foo bar baz\n'
    assert xonsh_execer_parse(code)


def test_simple_func_broken(xonsh_execer_parse):
    code = "def prompt():\n" "    return '{user}'.format(\n" "       user='me')\n"
    assert xonsh_execer_parse(code)


def test_bad_indent(xonsh_execer_parse):
    code = "if True:\n" "x = 1\n"
    with pytest.raises(SyntaxError):
        xonsh_execer_parse(code)


def test_comment_colon_ending(xonsh_execer_parse):
    code = "# this is a comment:\necho hello"
    assert xonsh_execer_parse(code)


def test_good_rhs_subproc():
    # nonsense but parsable
    code = "str().split() | ![grep exit]\n"
    assert code


def test_bad_rhs_subproc(xonsh_execer_parse):
    # nonsense but unparsable
    code = "str().split() | grep exit\n"
    with pytest.raises(SyntaxError):
        xonsh_execer_parse(code)


def test_indent_with_empty_line(xonsh_execer_parse):
    code = "if True:\n" "\n" "    some_command for_sub_process_mode\n"
    assert xonsh_execer_parse(code)


def test_command_in_func(xonsh_execer_parse):
    code = "def f():\n" "    echo hello\n"
    assert xonsh_execer_parse(code)


def test_command_in_func_with_comment(xonsh_execer_parse):
    code = "def f():\n" "    echo hello # comment\n"
    assert xonsh_execer_parse(code)


def test_pyeval_redirect(xonsh_execer_parse):
    code = 'echo @("foo") > bar\n'
    assert xonsh_execer_parse(code)


def test_pyeval_multiline_str(xonsh_execer_parse):
    code = 'echo @("""hello\nmom""")\n'
    assert xonsh_execer_parse(code)


def test_echo_comma(xonsh_execer_parse):
    code = "echo ,\n"
    assert xonsh_execer_parse(code)


def test_echo_comma_val(xonsh_execer_parse):
    code = "echo ,1\n"
    assert xonsh_execer_parse(code)


def test_echo_comma_2val(xonsh_execer_parse):
    code = "echo 1,2\n"
    assert xonsh_execer_parse(code)


def test_echo_line_cont(xonsh_execer_parse):
    code = 'echo "1 \\\n2"\n'
    assert xonsh_execer_parse(code)


@pytest.mark.parametrize(
    "code",
    [
        "echo a and \\\necho b\n",
        "echo a \\\n or echo b\n",
        "echo a \\\n or echo b and \\\n echo c\n",
        "if True:\\\n    echo a \\\n    b\n",
    ],
)
def test_two_echo_line_cont(code, xonsh_execer_parse):
    assert xonsh_execer_parse(code)


def test_eval_eol(check_eval):
    assert check_eval("0") and check_eval("0\n")


def test_annotated_assign(xonsh_execer_exec):
    # issue #3959 - didn't work because of `CtxAwareTransformer`
    assert xonsh_execer_exec("x : int = 42")


def test_exec_eol(xonsh_execer_exec):
    locs = dict()
    assert xonsh_execer_exec("a=0", locs=locs) and xonsh_execer_exec("a=0\n", locs=locs)


def test_exec_print(capsys, xonsh_execer_exec):
    ls = {"nested": "some long list"}
    xonsh_execer_exec("print(ls)", locs=dict(ls=ls))
    out, err = capsys.readouterr()
    assert out.strip() == repr(ls)


def test_exec_function_scope(xonsh_execer_exec):
    # issue 4363
    assert xonsh_execer_exec("x = 0; (lambda: x)()")
    assert xonsh_execer_exec("x = 0; [x for _ in [0]]")


def test_exec_scope_reuse(xonsh_execer_exec):
    # Scopes should not be reused between execs.
    # A first-pass incorrect solution to issue 4363 made this mistake.
    assert xonsh_execer_exec("x = 0")
    with pytest.raises(NameError):
        xonsh_execer_exec("print(x)")
