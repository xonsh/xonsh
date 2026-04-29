"""Tests the xonsh lexer. """

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
    code = "def prompt():\n    return '{user}'.format(user='me')\n"
    assert xonsh_execer_parse(code)


def test_lookup_alias(xonsh_execer_parse):
    code = 'def foo(a,  s=None):\n    return "bar"\n@(foo)\n'
    assert xonsh_execer_parse(code)


def test_lookup_anon_alias(xonsh_execer_parse):
    code = 'echo "hi" | @(lambda a, s=None: a[0]) foo bar baz\n'
    assert xonsh_execer_parse(code)


def test_simple_func_broken(xonsh_execer_parse):
    code = "def prompt():\n    return '{user}'.format(\n       user='me')\n"
    assert xonsh_execer_parse(code)


def test_bad_indent(xonsh_execer_parse):
    code = "if True:\nx = 1\n"
    with pytest.raises(SyntaxError):
        xonsh_execer_parse(code)


def test_keyword_arg_with_non_name_lhs_raises_syntax_error(xonsh_execer_parse):
    # Regression for #2574: `foo('spam'='eggs')` used to raise an opaque
    # AttributeError ('Constant' object has no attribute 'id') from inside
    # the parser action.  Match CPython's diagnostic message instead.
    code = "foo('spam'='eggs')\n"
    with pytest.raises(SyntaxError) as exc_info:
        xonsh_execer_parse(code)
    err = exc_info.value
    assert "expression cannot contain assignment" in err.msg
    assert err.lineno == 1


def test_non_default_after_default_arg_raises_syntax_error(xonsh_execer_parse):
    # Regression for #4915. Two layers of bug here:
    #   1. The parser's argument-list rule already detected the problem
    #      and stashed the message via `_set_error`, but PLY caught the
    #      bare SyntaxError as a parse-error signal, ran error recovery,
    #      and ultimately raised `unexpected dedent` on a later line —
    #      hiding the real error.
    #   2. The execer's recovery loop in `_try_parse` then dereferenced
    #      `lines[idx]` past EOF, surfacing a raw IndexError to the user.
    # After the fix the parser surfaces CPython-shaped diagnostics:
    #   `non-default argument follows default argument` on the offending
    #   line, with column pointing at the parameter.
    code = "def f(x=0,y):\n    print()\n"
    with pytest.raises(SyntaxError) as exc_info:
        xonsh_execer_parse(code)
    err = exc_info.value
    assert "non-default argument follows default argument" in err.msg
    assert err.lineno == 1


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
    code = "if True:\n\n    some_command for_sub_process_mode\n"
    assert xonsh_execer_parse(code)


def test_command_in_func(xonsh_execer_parse):
    code = "def f():\n    echo hello\n"
    assert xonsh_execer_parse(code)


def test_command_in_func_with_comment(xonsh_execer_parse):
    code = "def f():\n    echo hello # comment\n"
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


# Regression tests for GH-6354: when a function call followed by a
# subscript appears at statement level and its name is not yet tracked
# in scope (e.g. forward-referenced), CtxAwareTransformer used to hand
# the expression to try_subproc_toks, whose subproc_toks helper dropped
# the call and produced ``![[subscript]]``.  With ``$XONSH_SUBPROC_RAISE_ERROR``
# defaulting to True in 0.23 the resulting failed subprocess surfaces
# as a CalledProcessError; before 0.23 the bug was silent and the
# Python call was just never executed.  Either way the fix is that
# these expressions must stay as Python subscripts on calls.
@pytest.mark.parametrize(
    "expr",
    [
        "q()[0]",
        'q()["rows"]',
        "obj.method()[0]",
        "f(g())[0]",
        'pprint(q()["rows"])',
        "foo(bar()[0])",
    ],
)
def test_call_subscript_preserved_at_stmt_level(expr, xonsh_execer_parse):
    """Forward-referenced ``call()[subscript]`` must not collapse to a subproc."""
    tree = xonsh_execer_parse(expr + "\n")
    unparsed = pyast_unparse(tree)
    assert "subproc_captured_hiddenobject" not in unparsed, (
        f"{expr!r} was silently turned into a subproc call: {unparsed!r}"
    )


def test_forward_ref_call_subscript_in_function(xonsh_execer_parse):
    """Mirrors kafka-demo.xsh: the call is defined *after* the user (#6354)."""
    import ast as pyast

    code = (
        "def display():\n"
        "    from pprint import pprint\n"
        "    pprint(query_cratedb('SELECT 1;')['rows'])\n"
        "\n"
        "def query_cratedb(sql):\n"
        "    return {'rows': [1, 2, 3]}\n"
    )
    tree = xonsh_execer_parse(code)
    display = tree.body[0]
    assert isinstance(display, pyast.FunctionDef)
    # The display body should still contain a plain Python Expr with a
    # ``pprint(...)`` Call, not a subproc_captured_hiddenobject.
    stmts = pyast_unparse(display)
    assert "subproc_captured_hiddenobject" not in stmts
    assert "pprint(" in stmts


# The GH-6354 fix tightened subproc_toks on ``func()[subscript]``.  A
# side-effect was that ``f"{q()[0]}"`` at statement level produced a
# now-valid ``![f"{q()[0]}"]`` wrap and was mistakenly turned into a
# subprocess (before the fix it produced a broken wrap that silently
# fell back).  subproc_toks declines to wrap any statement whose first
# collected token is FSTRING_START — those are always Python
# expressions, never subprocess commands.
@pytest.mark.parametrize(
    "expr",
    [
        'f"{q()[0]}"',
        'f"{q()}"',
        'f"hi {x} {y}"',
    ],
)
def test_fstring_statement_stays_python(expr, xonsh_execer_parse):
    tree = xonsh_execer_parse(expr + "\n")
    assert "subproc_captured_hiddenobject" not in pyast_unparse(tree), (
        f"{expr!r} was turned into a subprocess"
    )


@pytest.mark.parametrize(
    "line",
    [
        "git fetch && @(x) && git branch",
        "git fetch || @(x) || git branch",
        "ls && @(['a', 'b']) && echo done",
    ],
)
def test_pyeval_in_andor_chain(line, xonsh_execer_parse):
    """``cmd && @(...) && cmd`` must parse without a SyntaxError."""
    assert xonsh_execer_parse(line + "\n")


def pyast_unparse(tree):
    """Return ast.unparse on the tree (helper for the tests above)."""
    import ast as pyast

    return pyast.unparse(tree)
