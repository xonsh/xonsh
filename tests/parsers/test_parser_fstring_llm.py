"""PEP 701 f-string tests: nested quotes, nested f-strings, xonsh $ syntax."""

import pytest

from xonsh.pytest.tools import VER_MAJOR_MINOR

_skip_pre_312 = pytest.mark.skipif(VER_MAJOR_MINOR < (3, 12), reason="PEP 701")


@_skip_pre_312
class TestPEP701FStrings:
    """PEP 701 f-string tokenization: nested quotes, nested f-strings, etc."""

    # -- basic f-string parsing (AST matches CPython) --

    def test_simple(self, check_ast):
        check_ast('f"hello"', run=False)

    def test_single_expr(self, check_ast):
        check_ast('f"{1+2}"', run=False)

    def test_text_and_expr(self, check_ast):
        check_ast('f"hello {42} world"', run=False)

    def test_multiple_exprs(self, check_ast):
        check_ast('f"{1} and {2} and {3}"', run=False)

    def test_empty_fstring(self, check_ast):
        check_ast('f""', run=False)

    # -- PEP 701: same-quote reuse inside {} --

    def test_reuse_double_quotes(self, check_ast):
        check_ast('f"{"hello"}"', run=False)

    def test_reuse_single_quotes(self, check_ast):
        check_ast("f'{'hello'}'", run=False)

    def test_reuse_quotes_method(self, check_ast):
        check_ast('f"{"qwe.py".removesuffix(".py")}.c"', run=False)

    def test_reuse_quotes_concat(self, check_ast):
        check_ast('f"{"one" + " " + "two"}"', run=False)

    def test_dict_access_same_quotes(self, check_ast):
        # Dict literal in f-string needs parens to avoid {{ ambiguity
        check_ast('f"{({"key": "val"})["key"]}"', run=False)

    # -- PEP 701: nested f-strings --

    def test_nested_fstring(self, check_ast):
        check_ast('f"{f"{1+1}"}"', run=False)

    def test_triple_nested_fstring(self, check_ast):
        check_ast('f"{f"{f"{42}"}"}"', run=False)

    def test_nested_fstring_with_text(self, check_ast):
        check_ast('f"outer {f"inner {f"deep {0}"}"}"', run=False)

    # -- format specs --

    def test_format_spec_float(self, check_ast):
        check_ast('f"{3.14:.2f}"', run=False)

    def test_format_spec_width(self, check_ast):
        check_ast('f"{42:>10}"', run=False)

    def test_format_spec_fill_align(self, check_ast):
        check_ast('f"{42:0>10}"', run=False)

    # -- conversions --

    def test_conversion_r(self, check_ast):
        check_ast('f"{"hello"!r}"', run=False)

    def test_conversion_s(self, check_ast):
        check_ast('f"{42!s}"', run=False)

    def test_conversion_a(self, check_ast):
        check_ast('f"{42!a}"', run=False)

    # -- self-documenting f"{x=}" --
    # NOTE: ast.unparse adds spaces (e.g., "1 + 1=" instead of "1+1="),
    # so we can't compare AST with CPython's (which uses source text).

    def test_self_doc_simple(self, check_ast):
        check_ast('f"{42=}"', run=False)

    def test_self_doc_format_spec(self, check_ast):
        check_ast('f"{42=:.5f}"', run=False)

    # -- escaped braces --

    def test_escaped_braces(self, check_ast):
        check_ast('f"{{literal}}"', run=False)

    def test_escaped_open_brace(self, check_ast):
        check_ast('f"{{ {42}"', run=False)

    def test_escaped_close_brace(self, check_ast):
        check_ast('f"{42} }}"', run=False)

    # -- triple-quoted f-strings --

    def test_triple_quoted(self, check_ast):
        check_ast('f"""hello {42} world"""', run=False)

    def test_triple_quoted_multiline(self, check_ast):
        check_ast('f"""line1\nline2"""', run=False)

    # -- string concatenation with f-strings --

    def test_concat_str_fstring(self, check_ast):
        check_ast('"hello " f"{"world"}"', run=False)

    def test_concat_fstring_str(self, check_ast):
        check_ast('f"{"hello"}" " world"', run=False)

    def test_concat_fstring_fstring(self, check_ast):
        check_ast('f"{1}" f"{2}"', run=False)

    # -- lambda inside f-string --

    def test_lambda(self, check_ast):
        check_ast('f"{(lambda: 42)()}"', run=False)

    # -- raw f-strings --

    def test_raw_fstring(self, check_ast):
        check_ast('rf"{42}\\n"', run=False)

    def test_raw_fstring_FR(self, check_ast):
        check_ast('FR"{42}\\n"', run=False)

    # -- prefix case variations --

    def test_prefix_F(self, check_ast):
        check_ast('F"{42}"', run=False)

    def test_prefix_fR(self, check_ast):
        check_ast('fR"{42}\\n"', run=False)


@_skip_pre_312
class TestPEP701XonshFStrings:
    """PEP 701 f-strings combined with xonsh-specific syntax."""

    # -- $VAR in f-strings --

    def test_dollar_env_var(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"{$HOME}"', run=False)

    def test_dollar_env_var_single_quote(self, check_xonsh_ast):
        check_xonsh_ast({}, "f'{$HOME}'", run=False)

    def test_dollar_env_var_with_text(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"home={$HOME}"', run=False)

    def test_multiple_dollar_vars(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"{$HOME} and {$USER}"', run=False)

    def test_dollar_var_with_regular_expr(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"{$HOME}/{1+1}"', run=False)

    # -- $VAR evaluated at runtime --

    def test_dollar_env_eval(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/foo/bar")
        obs = check_xonsh_ast({}, 'f"{$HOME}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "/foo/bar"

    def test_dollar_env_multiple_eval(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/home")
        monkeypatch.setitem(xsh.env, "USER", "alice")
        obs = check_xonsh_ast({}, 'f"{$HOME}/users/{$USER}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "/home/users/alice"

    # -- $VAR combined with PEP 701 quote reuse --

    def test_dollar_var_reuse_quotes(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/home")
        obs = check_xonsh_ast({}, 'f"{"prefix-" + $HOME}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "prefix-/home"

    # -- $VAR in nested f-strings --

    def test_dollar_var_nested_fstring(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "NAME", "world")
        obs = check_xonsh_ast({}, 'f"{"hello " + f"{$NAME}"}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "hello world"

    def test_dollar_var_nested_path(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/home")
        obs = check_xonsh_ast({}, 'f"{f"path={$HOME}"}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "path=/home"

    # -- $VAR with format spec --

    def test_dollar_var_format_spec(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "PI", "3.14159")
        obs = check_xonsh_ast({}, 'f"{float($PI):.2f}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "3.14"

    # -- ${} dynamic env var access --

    def test_dollar_brace_env(self, check_xonsh_ast):
        check_xonsh_ast({}, "f\"{${'HOME'}}\"", run=False)

    def test_dollar_brace_env_eval(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/foo/bar")
        obs = check_xonsh_ast({}, "f\"{${'HOME'}}\"", return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "/foo/bar"

    # -- pf"..." path f-strings --

    def test_pf_path_fstring(self, check_xonsh_ast):
        check_xonsh_ast({}, 'pf"{$HOME}"', run=False)

    def test_fp_path_fstring(self, check_xonsh_ast):
        check_xonsh_ast({}, 'fp"{$HOME}"', run=False)

    def test_pf_with_text(self, check_xonsh_ast):
        check_xonsh_ast({}, 'pf"{$HOME}/subdir"', run=False)

    # -- triple-quoted f-strings with xonsh --

    def test_triple_quoted_dollar(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"""{$HOME}"""', run=False)

    def test_triple_quoted_multiline_dollar(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/home")
        obs = check_xonsh_ast(
            {},
            'f"""path:\n{$HOME}\nend"""',
            return_obs=True,
        )
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "path:\n/home\nend"

    # -- $() command substitution in f-strings --

    def test_dollar_paren_in_fstring(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"{$(echo hello)}"', run=False)

    def test_dollar_paren_strip(self, check_xonsh_ast):
        check_xonsh_ast({}, 'f"{$(echo hello).strip()}"', run=False)

    # -- escaped braces with xonsh --

    def test_escaped_braces_with_dollar(self, check_xonsh_ast, xsh, monkeypatch):
        monkeypatch.setitem(xsh.env, "HOME", "/home")
        obs = check_xonsh_ast({}, 'f"{{literal}} {$HOME}"', return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == "{literal} /home"


@_skip_pre_312
class TestPEP701SubprocFStrings:
    """PEP 701 f-strings inside subprocess @() injections."""

    def test_subproc_at_string(self, check_xonsh_ast):
        """echo @('hello') — baseline, regular string."""
        check_xonsh_ast({}, '$[echo @("hello")]\n', run=False, mode="exec")

    def test_subproc_at_fstring_empty(self, check_xonsh_ast):
        """echo @(f'') — empty f-string."""
        check_xonsh_ast({}, "$[echo @(f'')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_text(self, check_xonsh_ast):
        """echo @(f'hello') — f-string without expressions."""
        check_xonsh_ast({}, "$[echo @(f'hello')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_expr(self, check_xonsh_ast):
        """echo @(f'{42}') — f-string with expression."""
        check_xonsh_ast({}, "$[echo @(f'{42}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_pep701_quotes(self, check_xonsh_ast):
        """echo @(f'{"word"}') — PEP 701 same-quote reuse."""
        check_xonsh_ast({}, '$[echo @(f"{"word"}")]\n', run=False, mode="exec")

    def test_subproc_at_fstring_method(self, check_xonsh_ast):
        """echo @(f'{"word".upper()}') — method call with reused quotes."""
        check_xonsh_ast(
            {}, '$[echo @(f"{"word".upper()}")]\n', run=False, mode="exec"
        )

    def test_subproc_at_fstring_nested(self, check_xonsh_ast):
        """echo @(f'{f"{1+1}"}') — nested f-string."""
        check_xonsh_ast(
            {}, '$[echo @(f"{f\"{1+1}\"}")]\n', run=False, mode="exec"
        )

    def test_subproc_at_fstring_format_spec(self, check_xonsh_ast):
        """echo @(f'{42:.2f}') — format spec."""
        check_xonsh_ast({}, "$[echo @(f'{42:.2f}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_escaped_braces(self, check_xonsh_ast):
        """echo @(f'{{x}}') — escaped braces."""
        check_xonsh_ast({}, "$[echo @(f'{{x}}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_dollar_var(self, check_xonsh_ast):
        """echo @(f'{$HOME}') — xonsh env var."""
        check_xonsh_ast({}, "$[echo @(f'{$HOME}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_dollar_with_text(self, check_xonsh_ast):
        """echo @(f'home={$HOME}') — env var with text."""
        check_xonsh_ast(
            {}, "$[echo @(f'home={$HOME}')]\n", run=False, mode="exec"
        )

    def test_subproc_at_fstring_dollar_paren(self, check_xonsh_ast):
        """echo @(f'{$(echo hi)}') — command substitution inside f-string."""
        check_xonsh_ast(
            {}, "$[echo @(f'{$(echo hi)}')]\n", run=False, mode="exec"
        )

    def test_subproc_at_fstring_concat(self, check_xonsh_ast):
        """echo @('a' + f'{"b"}') — string concat with f-string."""
        check_xonsh_ast(
            {}, '$[echo @("a" + f"{"b"}")]\n', run=False, mode="exec"
        )

    def test_subproc_fstring_multiple_dollar_paren(self, check_xonsh_ast):
        """echo f'{$(echo 1)} {$(echo 2)}' — f-string with two command subs."""
        check_xonsh_ast(
            {},
            """$[echo f"{$(echo 1).strip()} {$(echo 2).strip()}"]\n""",
            run=False,
            mode="exec",
        )
