"""Smoke tests for ``xonsh.style_tools``.

The module re-implements a tiny subset of pygments's token type so xonsh can
keep working when pygments is not available. These tests cover the parts
that don't actually need a live pygments install: the ``_TokenType`` algebra,
``color_by_name``, and ``partial_color_tokenize``.
"""

import pytest

from xonsh.style_tools import (
    DEFAULT_STYLE_DICT,
    Color,
    Token,
    _TokenType,
    color_by_name,
    norm_name,
    partial_color_tokenize,
    style_as_faded,
)


# --- _TokenType algebra ------------------------------------------------------


def test_token_root_is_token_type_instance():
    assert isinstance(Token, _TokenType)


def test_token_attribute_creates_subtoken_with_parent():
    tok = Token.Foo
    assert isinstance(tok, _TokenType)
    assert tok.parent is Token
    # the attribute is cached: accessing it twice yields the same object
    assert Token.Foo is tok


def test_token_attribute_caches_subtypes():
    Token.CachedAttr  # noqa: B018 — force creation
    assert any(t for t in Token.subtypes if t == Token.CachedAttr)


def test_token_split_returns_path_from_root():
    deep = Token.A.B.C
    assert deep.split() == [Token, Token.A, Token.A.B, Token.A.B.C]


def test_token_contains_self_and_subtokens():
    assert Token.Color in Token
    assert Token in Token  # self-containment
    assert Color.RED not in Token.Comment  # unrelated branches


def test_token_repr_starts_with_token():
    assert repr(Token).startswith("Token")
    assert repr(Token.Color.RED) == "Token.Color.RED"


def test_token_copy_returns_self_singleton():
    import copy

    tok = Token.SomeNew
    assert copy.copy(tok) is tok
    assert copy.deepcopy(tok) is tok


def test_lowercase_attribute_falls_through_to_tuple():
    """Lowercase attrs must NOT create new subtokens — they fall back to tuple."""
    with pytest.raises(AttributeError):
        Token.bogus_lowercase_attr


# --- norm_name ---------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("red", "RED"),
        ("Red", "RED"),
        ("#abc", "HEXABC"),
        ("BACKGROUND_RED", "BACKGROUND_RED"),
    ],
)
def test_norm_name(raw, expected):
    """Names are uppercased and ``#`` is rewritten as ``HEX``."""
    assert norm_name(raw) == expected


# --- color_by_name -----------------------------------------------------------


def test_color_by_name_reset():
    tok, fg, bg = color_by_name("RESET")
    assert tok is Color.RESET
    assert fg is None
    assert bg is None


def test_color_by_name_no_color_acts_like_reset(capsys):
    """``NO_COLOR`` is a deprecated alias for RESET — it still resolves to
    ``Color.RESET`` and prints a one-time warning to stderr."""
    # reset the one-shot warning flag so this test sees it
    import xonsh.color_tools as ct

    ct._NO_COLOR_WARNING_SHOWN = False
    tok, fg, bg = color_by_name("NO_COLOR")
    assert tok is Color.RESET
    assert fg is None
    assert bg is None
    err = capsys.readouterr().err
    assert "NO_COLOR" in err and "deprecated" in err.lower()


def test_color_by_name_simple_foreground():
    tok, fg, bg = color_by_name("RED")
    assert fg == "RED"
    assert bg is None
    assert tok is Color.RED


def test_color_by_name_simple_background():
    tok, fg, bg = color_by_name("BACKGROUND_BLUE")
    assert fg is None
    assert bg == "BACKGROUND_BLUE"
    assert tok is getattr(Color, "BACKGROUND_BLUE")


def test_color_by_name_combines_existing_fg_with_new_bg():
    """When a foreground is already set and a background comes in, the
    resulting token is named ``FG__BG``."""
    tok, fg, bg = color_by_name("BACKGROUND_GREEN", fg="RED", bg=None)
    assert fg == "RED"
    assert bg == "BACKGROUND_GREEN"
    assert tok is getattr(Color, "RED__BACKGROUND_GREEN")


# --- partial_color_tokenize -------------------------------------------------


def test_partial_color_tokenize_plain_text_yields_reset_token():
    toks = partial_color_tokenize("hello world")
    # plain text produces a single (Color.RESET, "hello world") token
    assert toks == [(Color.RESET, "hello world")]


def test_partial_color_tokenize_with_color_field():
    toks = partial_color_tokenize("{RED}hello{RESET}")
    # the RED segment then a RESET segment with empty trailing text
    types = [t for t, _ in toks]
    strings = [s for _, s in toks]
    assert Color.RED in types
    assert "hello" in strings


def test_partial_color_tokenize_preserves_non_color_fields():
    """Non-color fields are kept verbatim in the next segment's text."""
    toks = partial_color_tokenize("{user}@{host}")
    text = "".join(s for _, s in toks)
    assert text == "{user}@{host}"


def test_partial_color_tokenize_invalid_template_falls_back_to_reset():
    """An exception during tokenization yields a single RESET token with the
    raw template."""
    bad = "{unterminated"
    toks = partial_color_tokenize(bad)
    assert len(toks) == 1
    assert toks[0][0] is Color.RESET
    assert toks[0][1] == bad


# --- style_as_faded ---------------------------------------------------------


def test_style_as_faded_strips_colors_and_wraps_in_grey():
    out = style_as_faded("{RED}hello{RESET}")
    assert out.startswith("{RESET}{#d3d3d3}")
    assert out.endswith("{RESET}")
    assert "hello" in out
    # the original {RED} marker is gone
    assert "{RED}" not in out


# --- DEFAULT_STYLE_DICT ------------------------------------------------------


def test_default_style_dict_returns_str_for_known_token():
    # touching an attribute on the LazyObject triggers loading
    assert DEFAULT_STYLE_DICT[Token.Color.RED] == "ansired"


def test_default_style_dict_unknown_token_returns_empty_string():
    """The dict is a defaultdict — unknown tokens map to ``''``."""
    sentinel = Token.Color.SOMETHING_NEVER_DEFINED_XYZ
    assert DEFAULT_STYLE_DICT[sentinel] == ""
