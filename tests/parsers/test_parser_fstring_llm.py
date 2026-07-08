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

    @pytest.mark.parametrize(
        "inp",
        [
            'f"{42:=^10}"',  # '=' fill char with '^' align
            'f"{42:=>10}"',
            'f"{42:=<10}"',
            'f"{42:=+10}"',  # '=' align + '+' sign
            'f"{42:=10}"',  # '=' align + width
            'f"{42:=}"',  # bare '=' align
            'f"{42 := 10}"',  # ':' starts the spec even with surrounding spaces
            'f"{42:=^{3}}"',  # '=' fill with a nested-expr width
        ],
    )
    def test_format_spec_equals_fill(self, check_ast, inp):
        """A '=' right after ':' is a fill/align char, not the walrus operator.

        The tokenizer must not greedily read ':=' as COLONEQUAL at the top
        level of a replacement field (a real walrus needs parentheses).
        """
        check_ast(inp, run=False)

    @pytest.mark.parametrize(
        "inp, exp",
        [
            ("f'{v:=^11}'", "====123===="),
            ("f'{v:=>8}'", "=====123"),
            ("f'{v := 8}'", "     123"),  # ':' opens the spec; '= 8' is the spec
            ("f'{(v := 8)}'", "8"),  # a parenthesised walrus still assigns
        ],
    )
    def test_format_spec_equals_fill_render(self, parser, inp, exp):
        code = compile(parser.parse(inp), "<test>", "eval")
        assert eval(code, {"v": 123}) == exp

    def test_format_spec_nested_expr(self, check_ast):
        """f"{x:.{n}f}" — sub-expression inside format spec."""
        check_ast('f"{3.14159:.{3}f}"', run=False)

    def test_format_spec_multiple_nested_exprs(self, check_ast):
        """f"{x:{w}.{d}f}" — multiple sub-expressions in format spec."""
        check_ast('f"{3.14159:{10}.{3}f}"', run=False)

    def test_format_spec_followed_by_field(self, check_ast):
        """f"{a:02d}{b}" — format spec field followed by a plain field (issue #6389)."""
        check_ast('f"{5:02d}{6}"', run=False)

    def test_two_format_spec_fields(self, check_ast):
        """f"{a:02d}{b:03d}" — two consecutive format-spec fields (issue #6389)."""
        check_ast('f"{5:02d}{6:03d}"', run=False)

    def test_format_spec_then_text_then_field(self, check_ast):
        """f"{a:02d}lit{b}" — format spec, literal text, then a plain field."""
        check_ast('f"{5:02d}lit{6}"', run=False)

    def test_nested_format_spec_followed_by_field(self, check_ast):
        """f"{a:>{w}d}{b}" — nested-expr format spec followed by another field."""
        check_ast('f"{5:>{3}d}{6}"', run=False)

    # -- conversions --

    def test_conversion_r(self, check_ast):
        check_ast('f"{"hello"!r}"', run=False)

    def test_conversion_s(self, check_ast):
        check_ast('f"{42!s}"', run=False)

    def test_conversion_a(self, check_ast):
        check_ast('f"{42!a}"', run=False)

    # -- self-documenting f"{x=}" (debug syntax) --
    # The debug text is the verbatim source between '{' and the terminating
    # ':' / '!' / '}', so whitespace around '=' is preserved exactly as typed,
    # matching CPython's AST (issue #6536). ast.unparse() must NOT be used here
    # as it would normalise "1  +  1=" to "1 + 1=".

    @pytest.mark.parametrize(
        "inp",
        [
            'f"{42=}"',
            'f"{42 = }"',  # spaces on both sides of '='
            'f"{42 =}"',  # space only before '='
            'f"{42= }"',  # space only after '='
            'f"{ 42 =}"',  # leading space inside the braces
            'f"{1+1=}"',  # verbatim expression text (no normalisation)
            'f"{1  +  1 = }"',  # internal whitespace preserved
            'f"{42=:.5f}"',  # format spec
            'f"{42 = :.5f}"',  # whitespace + format spec (':' terminator)
            'f"{42=!r}"',  # conversion
            'f"{42 = !r}"',  # whitespace + conversion ('!' terminator)
            'f"{42 = !s:>10}"',  # whitespace + conversion + format spec
            'f"""{1 =\n}"""',  # multiline debug region keeps the newline
        ],
    )
    def test_self_doc(self, check_ast, inp):
        check_ast(inp, run=False)

    @pytest.mark.parametrize(
        "inp, exp",
        [
            # the exact spacing variants from issue #6536
            ('f"{v = }"', "v = 123"),
            ('f"{v =}"', "v =123"),
            ('f"{v= }"', "v= 123"),
            ('f"{v=}"', "v=123"),
            # leading / internal whitespace preserved verbatim
            ('f"{ v =}"', " v =123"),
            # conversion / format-spec terminators keep surrounding whitespace
            ('f"{v = !r}"', "v = 123"),
            ('f"{v = :>6}"', "v =    123"),
            # multiple debug fields and surrounding literal text
            ('f"a{v=}b{v=}c"', "av=123bv=123c"),
            ('f"pre {v = } post"', "pre v = 123 post"),
        ],
    )
    def test_self_doc_render(self, parser, inp, exp):
        code = compile(parser.parse(inp), "<test>", "eval")
        assert eval(code, {"v": 123}) == exp

    @pytest.mark.parametrize(
        "inp, exp",
        [
            # '=' as part of an operator must NOT be treated as debug syntax
            ("f'{x == y}'", "False"),
            ("f'{x != y}'", "True"),
            ("f'{x <= y}'", "True"),
            ("f'{x >= y}'", "False"),
            ("f'{(x := 5)}'", "5"),  # walrus, not debug
            ("f'{dict(a=1, b=2)}'", "{'a': 1, 'b': 2}"),  # kwargs, not debug
            # a comparison result that IS self-documented (debug '=' at the end)
            ("f'{x == y = }'", "x == y = False"),
            ("f'{x <= y = }'", "x <= y = True"),
            ("f'{x >= y=}'", "x >= y=False"),
            # self-documenting field nested inside another f-string
            ('f"{f"{x=}"}"', "x=7"),
        ],
    )
    def test_self_doc_boundary(self, parser, inp, exp):
        code = compile(parser.parse(inp), "<test>", "eval")
        assert eval(code, {"x": 7, "y": 42}) == exp

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

    # -- $VAR in self-documenting f"{$VAR=}" (issue #6536) --

    @pytest.mark.parametrize(
        "inp, exp",
        [
            ('f"{$HOME=}"', "$HOME='/foo/bar'"),
            ('f"{$HOME = }"', "$HOME = '/foo/bar'"),
            ('f"{$HOME =}"', "$HOME ='/foo/bar'"),
            ('f"{$HOME= }"', "$HOME= '/foo/bar'"),
        ],
    )
    def test_dollar_var_self_doc(self, check_xonsh_ast, xsh, monkeypatch, inp, exp):
        monkeypatch.setitem(xsh.env, "HOME", "/foo/bar")
        obs = check_xonsh_ast({}, inp, return_obs=True)
        code = compile(obs, "<test>", "eval")
        assert eval(code) == exp

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
        check_xonsh_ast({}, '$[echo @(f"{"word".upper()}")]\n', run=False, mode="exec")

    def test_subproc_at_fstring_nested(self, check_xonsh_ast):
        """echo @(f'{f"{1+1}"}') — nested f-string."""
        check_xonsh_ast({}, '$[echo @(f"{f"{1+1}"}")]\n', run=False, mode="exec")

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
        check_xonsh_ast({}, "$[echo @(f'home={$HOME}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_dollar_paren(self, check_xonsh_ast):
        """echo @(f'{$(echo hi)}') — command substitution inside f-string."""
        check_xonsh_ast({}, "$[echo @(f'{$(echo hi)}')]\n", run=False, mode="exec")

    def test_subproc_at_fstring_concat(self, check_xonsh_ast):
        """echo @('a' + f'{"b"}') — string concat with f-string."""
        check_xonsh_ast({}, '$[echo @("a" + f"{"b"}")]\n', run=False, mode="exec")

    def test_subproc_fstring_multiple_dollar_paren(self, check_xonsh_ast):
        """echo f'{$(echo 1)} {$(echo 2)}' — f-string with two command subs."""
        check_xonsh_ast(
            {},
            """$[echo f"{$(echo 1).strip()} {$(echo 2).strip()}"]\n""",
            run=False,
            mode="exec",
        )
