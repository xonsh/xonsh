"""PEP 701 f-string lexer tests: token sequences for all f-string patterns."""

import sys

import pytest

from xonsh.parsers.lexer import Lexer


_skip_pre_312 = pytest.mark.skipif(
    sys.version_info < (3, 12), reason="PEP 701 requires Python 3.12+"
)


def lex_input(inp: str):
    lex = Lexer()
    lex.input(inp)
    return list(lex)


def tok(t):
    """Extract (type, value, lexpos) from a LexToken."""
    return (t.type, t.value, t.lexpos)


def toks(inp: str):
    """Return list of (type, value, lexpos) for all tokens."""
    return [tok(t) for t in lex_input(inp)]


# ---- basic f-string structure ----


@_skip_pre_312
class TestFStringBasicLexer:

    def test_empty(self):
        assert toks('f""') == [
            ("FSTRING_START", 'f"', 0),
            ("FSTRING_END", '"', 2),
        ]

    def test_text_only(self):
        assert toks('f"hello"') == [
            ("FSTRING_START", 'f"', 0),
            ("FSTRING_MIDDLE", "hello", 2),
            ("FSTRING_END", '"', 7),
        ]

    def test_single_expr(self):
        assert toks('f"{x}"') == [
            ("FSTRING_START", 'f"', 0),
            ("LBRACE", "{", 2),
            ("NAME", "x", 3),
            ("RBRACE", "}", 4),
            ("FSTRING_END", '"', 5),
        ]

    def test_text_expr_text(self):
        assert toks('f"hello {x} world"') == [
            ("FSTRING_START", 'f"', 0),
            ("FSTRING_MIDDLE", "hello ", 2),
            ("LBRACE", "{", 8),
            ("NAME", "x", 9),
            ("RBRACE", "}", 10),
            ("FSTRING_MIDDLE", " world", 11),
            ("FSTRING_END", '"', 17),
        ]

    def test_two_exprs(self):
        result = toks('f"{a}+{b}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START", "LBRACE", "NAME", "RBRACE",
            "FSTRING_MIDDLE",
            "LBRACE", "NAME", "RBRACE", "FSTRING_END",
        ]

    def test_expr_only(self):
        result = toks('f"{42}"')
        assert result == [
            ("FSTRING_START", 'f"', 0),
            ("LBRACE", "{", 2),
            ("NUMBER", "42", 3),
            ("RBRACE", "}", 5),
            ("FSTRING_END", '"', 6),
        ]

    def test_single_quote(self):
        assert toks("f'hello'") == [
            ("FSTRING_START", "f'", 0),
            ("FSTRING_MIDDLE", "hello", 2),
            ("FSTRING_END", "'", 7),
        ]


# ---- PEP 701: reuse same quotes ----


@_skip_pre_312
class TestFStringQuoteReuseLexer:

    def test_double_inside_double(self):
        result = toks('f"{"hello"}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START", "LBRACE",
            "STRING",
            "RBRACE", "FSTRING_END",
        ]
        assert result[2] == ("STRING", '"hello"', 3)

    def test_single_inside_single(self):
        result = toks("f'{'hello'}'")
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START", "LBRACE",
            "STRING",
            "RBRACE", "FSTRING_END",
        ]

    def test_method_call_reuse(self):
        result = toks('f"{"ab".upper()}"')
        types = [t[0] for t in result]
        assert "STRING" in types
        assert "PERIOD" in types
        assert "NAME" in types


# ---- nested f-strings ----


@_skip_pre_312
class TestFStringNestedLexer:

    def test_one_level(self):
        result = toks('f"{f"{1}"}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START", "LBRACE",
            "FSTRING_START", "LBRACE", "NUMBER", "RBRACE", "FSTRING_END",
            "RBRACE", "FSTRING_END",
        ]

    def test_two_levels(self):
        result = toks('f"{f"{f"{0}"}"}"')
        types = [t[0] for t in result]
        # 3 FSTRING_START and 3 FSTRING_END
        assert types.count("FSTRING_START") == 3
        assert types.count("FSTRING_END") == 3

    def test_nested_with_text(self):
        result = toks('f"a{f"b{f"c"}"}"')
        types = [t[0] for t in result]
        middles = [t for t in result if t[0] == "FSTRING_MIDDLE"]
        assert [m[1] for m in middles] == ["a", "b", "c"]


# ---- format specs ----


@_skip_pre_312
class TestFStringFormatSpecLexer:

    def test_simple_spec(self):
        result = toks('f"{x:.2f}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START",
            "LBRACE", "NAME", "COLON", "FSTRING_MIDDLE", "RBRACE",
            "FSTRING_END",
        ]
        # The format spec text is FSTRING_MIDDLE
        assert result[4] == ("FSTRING_MIDDLE", ".2f", 5)

    def test_width_spec(self):
        result = toks('f"{x:>10}"')
        types = [t[0] for t in result]
        assert "COLON" in types
        assert "FSTRING_MIDDLE" in types

    def test_fill_align_spec(self):
        result = toks('f"{x:0>10d}"')
        spec_middles = [t for t in toks('f"{x:0>10d}"') if t[0] == "FSTRING_MIDDLE"]
        assert spec_middles[0][1] == "0>10d"


# ---- conversions ----


@_skip_pre_312
class TestFStringConversionLexer:

    def test_bang_r(self):
        result = toks('f"{x!r}"')
        types = [t[0] for t in result]
        # ! is ERRORTOKEN in xonsh tokenizer (same as CPython)
        assert "NAME" in types  # 'r' after '!'

    def test_bang_s(self):
        result = toks('f"{x!s}"')
        values = [t[1] for t in result]
        assert "s" in values

    def test_bang_a(self):
        result = toks('f"{x!a}"')
        values = [t[1] for t in result]
        assert "a" in values


# ---- self-documenting f"{x=}" ----


@_skip_pre_312
class TestFStringSelfDocLexer:

    def test_simple_selfdoc(self):
        result = toks('f"{x=}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START",
            "LBRACE", "NAME", "EQUALS", "RBRACE",
            "FSTRING_END",
        ]

    def test_selfdoc_with_spec(self):
        result = toks('f"{x=:.2f}"')
        types = [t[0] for t in result]
        assert "EQUALS" in types
        assert "COLON" in types
        assert "FSTRING_MIDDLE" in types


# ---- escaped braces ----


@_skip_pre_312
class TestFStringEscapedBracesLexer:

    def test_double_open_brace(self):
        result = toks('f"{{x}}"')
        types = [t[0] for t in result]
        # {{ and }} are literal braces → FSTRING_MIDDLE
        assert "LBRACE" not in types
        assert "RBRACE" not in types
        middles = [t[1] for t in result if t[0] == "FSTRING_MIDDLE"]
        assert "".join(middles) == "{x}"

    def test_escaped_open_before_expr(self):
        result = toks('f"{{ {42}"')
        types = [t[0] for t in result]
        # {{ → FSTRING_MIDDLE "{", then space → FSTRING_MIDDLE, then {42}
        assert "LBRACE" in types
        assert "NUMBER" in types

    def test_escaped_close_after_expr(self):
        result = toks('f"{42} }}"')
        types = [t[0] for t in result]
        assert "RBRACE" in types
        middles = [t[1] for t in result if t[0] == "FSTRING_MIDDLE"]
        assert any("}" in m for m in middles)


# ---- triple-quoted f-strings ----


@_skip_pre_312
class TestFStringTripleQuotedLexer:

    def test_triple_double(self):
        result = toks('f"""hello"""')
        assert result == [
            ("FSTRING_START", 'f"""', 0),
            ("FSTRING_MIDDLE", "hello", 4),
            ("FSTRING_END", '"""', 9),
        ]

    def test_triple_single(self):
        result = toks("f'''hello'''")
        assert result == [
            ("FSTRING_START", "f'''", 0),
            ("FSTRING_MIDDLE", "hello", 4),
            ("FSTRING_END", "'''", 9),
        ]

    def test_triple_with_expr(self):
        result = toks('f"""a {x} b"""')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START", "FSTRING_MIDDLE",
            "LBRACE", "NAME", "RBRACE",
            "FSTRING_MIDDLE", "FSTRING_END",
        ]

    def test_triple_multiline(self):
        result = toks('f"""line1\n{x}\nline2"""')
        types = [t[0] for t in result]
        assert types.count("FSTRING_MIDDLE") == 2  # "line1\n" and "\nline2"
        assert "LBRACE" in types


# ---- prefix variations ----


@_skip_pre_312
class TestFStringPrefixLexer:

    def test_F_upper(self):
        result = toks('F"{x}"')
        assert result[0] == ("FSTRING_START", 'F"', 0)

    def test_fr_prefix(self):
        result = toks('fr"{x}"')
        assert result[0] == ("FSTRING_START", 'fr"', 0)

    def test_rf_prefix(self):
        result = toks('rf"{x}"')
        assert result[0] == ("FSTRING_START", 'rf"', 0)

    def test_FR_prefix(self):
        result = toks('FR"{x}"')
        assert result[0] == ("FSTRING_START", 'FR"', 0)

    def test_fR_prefix(self):
        result = toks('fR"{x}"')
        assert result[0] == ("FSTRING_START", 'fR"', 0)

    def test_Rf_prefix(self):
        result = toks('Rf"{x}"')
        assert result[0] == ("FSTRING_START", 'Rf"', 0)


# ---- expression complexity ----


@_skip_pre_312
class TestFStringExprLexer:

    def test_binary_op(self):
        result = toks('f"{a + b}"')
        types = [t[0] for t in result]
        assert "NAME" in types
        assert "PLUS" in types

    def test_comparison(self):
        result = toks('f"{a > b}"')
        types = [t[0] for t in result]
        assert "GT" in types

    def test_function_call(self):
        result = toks('f"{foo(1, 2)}"')
        types = [t[0] for t in result]
        assert "LPAREN" in types
        assert "RPAREN" in types
        assert "COMMA" in types

    def test_subscript(self):
        result = toks('f"{a[0]}"')
        types = [t[0] for t in result]
        assert "LBRACKET" in types
        assert "RBRACKET" in types

    def test_ternary(self):
        result = toks('f"{a if b else c}"')
        types = [t[0] for t in result]
        assert "IF" in types
        assert "ELSE" in types

    def test_dict_in_parens(self):
        result = toks('f"{({1: 2})[1]}"')
        types = [t[0] for t in result]
        assert "LPAREN" in types
        assert "COLON" in types

    def test_lambda(self):
        result = toks('f"{(lambda: 1)()}"')
        types = [t[0] for t in result]
        assert "LAMBDA" in types


# ---- xonsh syntax inside f-strings ----


@_skip_pre_312
class TestFStringXonshLexer:

    def test_dollar_name(self):
        result = toks('f"{$HOME}"')
        types = [t[0] for t in result]
        assert types == [
            "FSTRING_START",
            "LBRACE", "DOLLAR_NAME", "RBRACE",
            "FSTRING_END",
        ]
        assert result[2] == ("DOLLAR_NAME", "$HOME", 3)

    def test_dollar_name_with_text(self):
        result = toks('f"path={$HOME}"')
        types = [t[0] for t in result]
        assert "FSTRING_MIDDLE" in types
        assert "DOLLAR_NAME" in types
        middles = [t for t in result if t[0] == "FSTRING_MIDDLE"]
        assert middles[0][1] == "path="

    def test_dollar_name_multiple(self):
        result = toks('f"{$HOME}/{$USER}"')
        dollars = [t for t in result if t[0] == "DOLLAR_NAME"]
        assert len(dollars) == 2
        assert dollars[0][1] == "$HOME"
        assert dollars[1][1] == "$USER"

    def test_dollar_brace(self):
        """${...} dynamic env var access."""
        result = toks("f\"{${'HOME'}}\"")
        types = [t[0] for t in result]
        assert "DOLLAR_LBRACE" in types
        assert "STRING" in types

    def test_dollar_paren(self):
        """$() command substitution."""
        result = toks('f"{$(echo hello)}"')
        types = [t[0] for t in result]
        assert "DOLLAR_LPAREN" in types

    def test_dollar_paren_method(self):
        result = toks('f"{$(echo hello).strip()}"')
        types = [t[0] for t in result]
        assert "DOLLAR_LPAREN" in types
        assert "PERIOD" in types

    def test_dollar_name_in_nested_fstring(self):
        result = toks('f"{f"{$HOME}"}"')
        types = [t[0] for t in result]
        assert types.count("FSTRING_START") == 2
        assert "DOLLAR_NAME" in types

    def test_dollar_name_mixed_with_expr(self):
        result = toks('f"{$HOME + \"/bin\"}"')
        types = [t[0] for t in result]
        assert "DOLLAR_NAME" in types
        assert "PLUS" in types
        assert "STRING" in types


# ---- xonsh pf"..." path f-strings ----


@_skip_pre_312
class TestFStringPathLexer:

    def test_pf_prefix(self):
        result = toks('pf"{x}"')
        assert result[0] == ("FSTRING_START", 'pf"', 0)

    def test_fp_prefix(self):
        result = toks('fp"{x}"')
        assert result[0] == ("FSTRING_START", 'fp"', 0)

    def test_pF_prefix(self):
        result = toks('pF"{x}"')
        assert result[0] == ("FSTRING_START", 'pF"', 0)

    def test_Fp_prefix(self):
        result = toks('Fp"{x}"')
        assert result[0] == ("FSTRING_START", 'Fp"', 0)

    def test_pf_with_dollar(self):
        result = toks('pf"{$HOME}/bin"')
        types = [t[0] for t in result]
        assert "FSTRING_START" in types
        assert "DOLLAR_NAME" in types
        assert "FSTRING_MIDDLE" in types

    def test_pf_triple(self):
        result = toks("pf'''{x}'''")
        assert result[0] == ("FSTRING_START", "pf'''", 0)
        assert result[-1] == ("FSTRING_END", "'''", 8)


# ---- string concat with f-strings ----


@_skip_pre_312
class TestFStringConcatLexer:

    def test_str_then_fstring(self):
        result = toks('"hello " f"{x}"')
        types = [t[0] for t in result]
        assert types[0] == "STRING"
        assert "FSTRING_START" in types

    def test_fstring_then_str(self):
        result = toks('f"{x}" "hello"')
        types = [t[0] for t in result]
        assert types[0] == "FSTRING_START"
        assert "STRING" in types

    def test_fstring_fstring(self):
        result = toks('f"{a}" f"{b}"')
        types = [t[0] for t in result]
        assert types.count("FSTRING_START") == 2
        assert types.count("FSTRING_END") == 2
