"""Tests for the xonsh formatter engine (``xonsh.formatter.core``)."""

from __future__ import annotations

import io

import pytest

from xonsh.formatter import format_source
from xonsh.formatter.core import FormatError
from xonsh.parsers.tokenize import (
    DEDENT,
    ENCODING,
    ENDMARKER,
    INDENT,
    NEWLINE,
    NL,
    tokenize,
)


def _token_skeleton(src: str) -> list[tuple[int, str]]:
    """Return ``[(token_type, token_string)]`` for ``src``, dropping
    whitespace-bearing tokens whose value the formatter is allowed to
    rewrite (INDENT spelling, NL placement, ENCODING). The remaining
    sequence must be invariant under formatting if the formatter is
    behaving correctly."""
    skip = {ENCODING, INDENT, DEDENT, NEWLINE, NL, ENDMARKER}
    out = []
    if not src.endswith("\n"):
        src = src + "\n"
    rl = io.BytesIO(src.encode("utf-8")).readline
    for tok in tokenize(rl, tolerant=True):
        if tok.type in skip:
            continue
        out.append((tok.type, tok.string))
    return out


# ---------------------------------------------------------------------
# Basic spacing / operators
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src, expected",
    [
        ("x=1\n", "x = 1\n"),
        ("x  =   1\n", "x = 1\n"),
        ("x = 1\n", "x = 1\n"),
        ("a==b\n", "a == b\n"),
        ("a!=b\n", "a != b\n"),
        ("a+=1\n", "a += 1\n"),
        ("a*=2\n", "a *= 2\n"),
        ("a:=1\n", "a := 1\n"),
        ("def f()->None: pass\n", "def f() -> None: pass\n"),
    ],
)
def test_assignment_and_comparison_get_spaces(src, expected):
    # ``a>=b`` / ``a<=b`` without surrounding whitespace are *not*
    # in this list: the xonsh tokenizer treats ``name>`` as an
    # IO-redirect token (think ``2>err``), so a bare ``a>=b`` cannot
    # be losslessly distinguished from a redirect at the token level.
    # When the user writes proper xonsh comparisons (with at least one
    # space — ``a >= b``) the operator arrives as a single OP token
    # and the formatter handles it; that case is exercised by
    # :func:`test_comparison_with_whitespace_kept` below.
    assert format_source(src) == expected


@pytest.mark.parametrize(
    "src",
    [
        "a >= b\n",
        "a <= b\n",
        "a > b\n",
        "a < b\n",
    ],
)
def test_comparison_with_whitespace_kept(src):
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src",
    [
        "f(x=1)\n",
        "def f(x=1): pass\n",
        "def f(a, b=2, c=3): pass\n",
        "lambda x=1: x\n",
        "lambda: 1\n",
        "lambda x, y=2: x + y\n",
    ],
)
def test_kwargs_and_defaults_keep_glued_equals(src):
    """``=`` inside parens or in ``lambda`` params must stay glued."""
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src, expected",
    [
        ("a,b,c\n", "a, b, c\n"),
        ("a , b , c\n", "a, b, c\n"),
        ("a;b;c\n", "a; b; c\n"),
        ("(a,)\n", "(a,)\n"),  # trailing comma before closer
        ("[1,2,3]\n", "[1, 2, 3]\n"),
        ("f( x , y )\n", "f(x, y)\n"),
        ("{ 'a' : 1 , 'b' : 2 }\n", "{'a': 1, 'b': 2}\n"),
    ],
)
def test_comma_semicolon_spacing(src, expected):
    assert format_source(src) == expected


@pytest.mark.parametrize(
    "src",
    [
        "a[1:2]\n",
        "a[1:2:3]\n",
        "a[:5]\n",
        "a[::-1]\n",
        "a[i:j, k:l]\n",
    ],
)
def test_slice_colons_stay_glued(src):
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src, expected",
    [
        ("{a:1}\n", "{a: 1}\n"),
        ("{a:1, b:2}\n", "{a: 1, b: 2}\n"),
        ("def f(x:int, y:str): pass\n", "def f(x: int, y: str): pass\n"),
    ],
)
def test_colon_in_dict_or_annotation_gets_space_after(src, expected):
    assert format_source(src) == expected


# ---------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        # Comment bodies are preserved byte-for-byte. Users routinely
        # keep commented-out code as ``#def foo():`` and the formatter
        # must not insert a space after ``#``.
        "#hello\n",
        "# hello\n",
        "#  hello\n",
        "#\n",
        "#def _foo(args):\n",
        "#class Bar:\n",
        "#noqa\n",
        "#:\n",
        "# -*- coding: utf-8 -*-\n",
    ],
)
def test_comment_body_preserved_verbatim(src):
    assert format_source(src) == src


def test_shebang_preserved():
    src = "#!/usr/bin/env xonsh\nx = 1\n"
    assert format_source(src) == src


def test_inline_comment_gets_two_spaces_padding_only():
    """The *padding* before an inline comment is normalized to two
    spaces (PEP 8), but the comment body itself is left untouched."""
    src = "x = 1 # ok\n"
    assert format_source(src) == "x = 1  # ok\n"

    src2 = "x = 1  #ok\n"
    # Body kept as-is — including the missing space after ``#``.
    assert format_source(src2) == "x = 1  #ok\n"


def test_trailing_comment_outside_block_indented_at_outer_level():
    src = "def f():\n    pass\n# trailing\n"
    expected = "def f():\n    pass\n# trailing\n"
    assert format_source(src) == expected


def test_comment_between_methods_at_class_level():
    src = (
        "class C:\n"
        "    def a(self):\n"
        "        pass\n"
        "    # between\n"
        "    def b(self):\n"
        "        pass\n"
    )
    out = format_source(src)
    # The "# between" line must be at 1-level indent (4 spaces),
    # not 2-level.
    assert "    # between\n" in out
    assert "        # between\n" not in out


def test_tab_indented_comment_in_space_indented_file():
    """Mixed tab/space indentation: a comment indented with a single
    TAB in a file whose code uses four-space indentation must resolve
    to indent level 1 (one tab = one level), not get stranded at
    column 0 because a single tab character is shorter than the
    detected source-indent width."""
    src = (
        "def install_mac():\n"
        "    if cond:\n"
        "        printx('hello')\n"
        "\t# comment indented with a tab\n"
        "        body()\n"
    )
    expected = (
        "def install_mac():\n"
        "    if cond:\n"
        "        printx('hello')\n"
        "    # comment indented with a tab\n"
        "        body()\n"
    )
    assert format_source(src) == expected


def test_leading_comment_in_function_body():
    src = "def f():\n    # leading\n    pass\n"
    out = format_source(src)
    assert "    # leading\n" in out


# ---------------------------------------------------------------------
# Indentation
# ---------------------------------------------------------------------


def test_tabs_normalized_to_four_spaces():
    src = "def f():\n\tif x:\n\t\treturn 1\n"
    out = format_source(src)
    assert "\t" not in out
    assert "    if x:\n" in out
    assert "        return 1\n" in out


def test_two_space_indent_renormalized_to_four():
    src = "def f():\n  if x:\n    return 1\n"
    out = format_source(src)
    assert "    if x:\n" in out
    assert "        return 1\n" in out


def test_custom_indent():
    src = "def f():\n    pass\n"
    out = format_source(src, indent="  ")
    assert "  pass\n" in out


# ---------------------------------------------------------------------
# Blank lines
# ---------------------------------------------------------------------


def test_excess_top_level_blank_lines_collapsed_to_two():
    src = "x = 1\n\n\n\n\ny = 2\n"
    assert format_source(src) == "x = 1\n\n\ny = 2\n"


def test_excess_nested_blank_lines_collapsed_to_one():
    src = "def f():\n    a = 1\n\n\n\n    b = 2\n"
    assert format_source(src) == "def f():\n    a = 1\n\n    b = 2\n"


def test_trailing_newlines_collapsed_to_single():
    src = "x = 1\n\n\n\n"
    assert format_source(src) == "x = 1\n"


def test_missing_trailing_newline_added():
    src = "x = 1"
    assert format_source(src) == "x = 1\n"


def test_empty_source():
    assert format_source("") == ""


# ---------------------------------------------------------------------
# Trailing whitespace
# ---------------------------------------------------------------------


def test_trailing_whitespace_stripped():
    src = "x = 1   \ny = 2\t\n"
    assert format_source(src) == "x = 1\ny = 2\n"


# ---------------------------------------------------------------------
# xonsh-specific syntax preservation
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "x = $(ls -la)\n",
        "x = $[ls -la]\n",
        "x = !(grep py)\n",
        "x = ![grep py]\n",
        "echo ${HOME}\n",
        "x = @(some_var)\n",
        "x = @$(echo a)\n",
        "echo a && echo b\n",
        "echo a || echo b\n",
        "cat file.txt | grep py\n",
        "cmd > out.txt\n",
        "cmd 2> err.txt\n",
        "cmd >> out.txt\n",
        "cmd 2>&1\n",
    ],
)
def test_xonsh_subprocess_syntax_preserved(src):
    """xonsh-specific tokens must round-trip unchanged."""
    assert format_source(src) == src


def test_glob_path_preserved():
    # Search-path glob token (g`...`, p`...`, r`...`)
    src = "for f in g`*.py`:\n    print(f)\n"
    assert format_source(src) == src


def test_nested_subprocess_preserved():
    src = "x = $(echo $(date))\n"
    assert format_source(src) == src


def test_subprocess_inside_python_expr():
    src = "x = [f for f in $(ls).split()]\n"
    assert format_source(src) == src


# ---------------------------------------------------------------------
# Subprocess statements & macros (https://xon.sh/macros.html)
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        # ``--flag=value`` arguments stay glued — no ``=`` spacing.
        "echo 1 2 --qwe=123\n",
        "cmd --flag=value other\n",
        "cmd -a -b -c\n",
        "cmd -aBC --long-flag\n",
    ],
)
def test_subprocess_keeps_kwarg_flags_glued(src):
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src, expected",
    [
        # Multiple spaces between subprocess args collapse to one,
        # mirroring the behaviour of ``$(...)`` captures and matching
        # the shell's own treatment of inter-arg whitespace.
        (
            'echo 123          @("""hello {x}""")\n',
            'echo 123 @("""hello {x}""")\n',
        ),
        ("echo a   b --flag=v\n", "echo a b --flag=v\n"),
        ("cmd  arg1   arg2\n", "cmd arg1 arg2\n"),
        # Inside an ``if`` body — heuristic still fires.
        (
            "if x:\n    echo a   b --flag=v\n",
            "if x:\n    echo a b --flag=v\n",
        ),
    ],
)
def test_subprocess_collapses_inter_arg_whitespace(src, expected):
    assert format_source(src) == expected


@pytest.mark.parametrize(
    "src",
    [
        # Alias macro (``name!``): the args after the bang are raw text
        # — runs of whitespace between them must be preserved.
        "echo! 1   2\n",
        "echo!  hello   world\n",
        # Function macro ``name!(args)`` — body is raw text.
        "f!(any  raw  text)\n",
        "f!(no   change   here)\n",
    ],
)
def test_macros_keep_args_verbatim(src):
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src",
    [
        # Block macro: ``with! ctx:`` — the bang is glued to ``with``,
        # the keyword-force-space rule must not pry them apart.
        "with! qwe:\n    pass\n",
        # Bang glued to NAME (alias macro) — already handled by
        # alias-macro detection, included here for completeness.
        "echo!stuff\n",
    ],
)
def test_glued_bang_macro_marker_keeps_no_space(src):
    assert format_source(src) == src


def test_user_written_spaces_around_subproc_equals_preserved():
    """``--flag = value`` (with user-typed spaces around ``=``) keeps
    its shape — neither added nor removed by the formatter."""
    src = "echo 1 2 --qwe = 123\n"
    assert format_source(src) == src


@pytest.mark.parametrize(
    "src, expected",
    [
        # Single ``\``-continuation: replace whatever leading
        # whitespace the user typed on the continuation line with the
        # standard indent (one level past the statement's base).
        (
            "echo 1 2 \\\n --qwe=123\n",
            "echo 1 2 \\\n    --qwe=123\n",
        ),
        (
            "cmd 1 2 \\\n          --qwe=123\n",
            "cmd 1 2 \\\n    --qwe=123\n",
        ),
        # Multiple chained continuations.
        (
            "echo 1 2 \\\n --qwe --qwe \\\n          --asd=123\n",
            "echo 1 2 \\\n    --qwe --qwe \\\n    --asd=123\n",
        ),
        # Continuation inside a nested block — indent goes one level
        # deeper than the surrounding ``def``/``if`` body.
        (
            "if x:\n    echo 1 \\\n        --flag=v\n",
            "if x:\n    echo 1 \\\n        --flag=v\n",
        ),
    ],
)
def test_subprocess_continuation_uses_standard_indent(src, expected):
    assert format_source(src) == expected


def test_subprocess_capture_collapses_inner_whitespace():
    """``$(...)`` and ``!(...)`` capture *expressions* (Python value =
    captured pipeline) get the regular paren-aware Python rules — runs
    of whitespace between args collapse to a single space, while string
    contents and ``--flag=value`` syntax are preserved by the existing
    rules. ``@(...)`` switches back to a fully Python eval, so its
    leading whitespace also collapses."""
    src = '$(echo 1 2 --qwe="        123"        --asd=@(      f"{$HOME}"))\n'
    expected = '$(echo 1 2 --qwe="        123" --asd=@(f"{$HOME}"))\n'
    assert format_source(src) == expected


def test_subprocess_capture_preserves_strings_and_kwargs():
    src = '$(cmd --flag="a   b" other)\n'
    assert format_source(src) == src


def test_bang_capture_collapses_inner_whitespace():
    src = "!(echo a    b)\n"
    assert format_source(src) == "!(echo a b)\n"


@pytest.mark.parametrize(
    "src, expected",
    [
        # ``or`` aligned with ``if``: same column under both.
        (
            "    if (a) \\\n    or (b):\n        pass\n",
            "    if (a) \\\n    or (b):\n        pass\n",
        ),
        # Continuation 4 spaces deeper than the statement's indent.
        (
            "    if (a) \\\n        or (b):\n        pass\n",
            "    if (a) \\\n        or (b):\n        pass\n",
        ),
        # Top level, continuation indented one level.
        (
            "if (a) \\\n    or (b):\n    pass\n",
            "if (a) \\\n    or (b):\n    pass\n",
        ),
        # 12-space source indent (3 indent units of 4 chars each in the
        # source's own scheme): formatter normalizes to 4-space indent,
        # the continuation must stay aligned with the normalized
        # statement indent, not stranded at the original source column.
        (
            "            if (a) \\\n            or (b):\n                pass\n",
            "    if (a) \\\n    or (b):\n        pass\n",
        ),
    ],
)
def test_python_backslash_continuation_alignment_preserved(src, expected):
    assert format_source(src) == expected


def test_subproc_line_with_triple_quoted_fstring_arg_preserved():
    """A subprocess line that takes a multi-line triple-quoted f-string
    as one of its arguments must round-trip: the xonsh tokenizer
    reports inverted positions for multi-line ``FSTRING_MIDDLE`` tokens
    (start col > end col), and previously the verbatim ``_raw_between``
    mode in subprocess context would synthesize a fake "gap" out of
    those positions and end up duplicating the entire f-string body.
    Now the f-string-segment glue rule wins over any verbatim mode."""
    src = (
        'docker run --rm -it -h @(host) xonsh/xonsh bash -lc @(f"""\n'
        "    set -e\n"
        "    git clone --depth 1 --branch {branch} {url} /tmp/xonsh\n"
        "    exec bash\n"
        '    """)\n'
    )
    assert format_source(src) == src


def test_dollar_subscript_at_top_level_assignment():
    """``$VAR = 'value'`` is a Python-level env assignment — gets the
    usual ``=`` spacing, not subprocess treatment."""
    src = "$PATH='/usr/bin'\n"
    assert format_source(src) == "$PATH = '/usr/bin'\n"


@pytest.mark.parametrize(
    "src, expected",
    [
        # Plain Python lines must NOT be misclassified as subprocess
        # — the ``=`` rule and the indent / comma normalisation should
        # apply as usual.
        ("x=1\n", "x = 1\n"),
        ("x = 1\n", "x = 1\n"),
        ("f(x=1)\n", "f(x=1)\n"),
        ("a.b.c\n", "a.b.c\n"),
        ("x and y\n", "x and y\n"),
        ("x or y\n", "x or y\n"),
        ("x is None\n", "x is None\n"),
        ("x in s\n", "x in s\n"),
        ("x not in s\n", "x not in s\n"),
        ("x - 1\n", "x - 1\n"),
        ("x + y\n", "x + y\n"),
        ("True == False\n", "True == False\n"),
        ("if x:\n    pass\n", "if x:\n    pass\n"),
        ("lambda x=1: x\n", "lambda x=1: x\n"),
        (
            "match foo:\n    case _:\n        pass\n",
            "match foo:\n    case _:\n        pass\n",
        ),
        ("type X = int\n", "type X = int\n"),
    ],
)
def test_python_lines_not_misclassified_as_subprocess(src, expected):
    assert format_source(src) == expected


def test_env_var_assignment():
    src = "$PATH = '/usr/bin'\n"
    assert format_source(src) == src


# ---------------------------------------------------------------------
# F-strings
# ---------------------------------------------------------------------


def test_fstring_preserved():
    src = 'x = f"hello {name}"\n'
    assert format_source(src) == src


def test_fstring_with_format_spec():
    src = 'x = f"{value:>10.2f}"\n'
    assert format_source(src) == src


def test_fstring_double_brace_escape_preserved():
    """``{{`` and ``}}`` are the f-string escapes for literal braces.

    The tokenizer emits ``FSTRING_MIDDLE`` with the *decoded* value
    (one brace, not two), so a naive emitter would silently change
    the format string. The formatter must extract the original source
    bytes for ``FSTRING_MIDDLE`` to keep the escapes intact.
    """
    src = 'x = f"{{{name}}}{value}{{LITERAL}}"\n'
    assert format_source(src) == src


def test_fstring_format_spec_with_braces_preserved():
    src = 'x = f"|{{:<{width}}}|"\n'
    assert format_source(src) == src


def test_fstring_colon_between_expressions_preserved():
    """``f"{a}:{b}"`` has a literal ``:`` between two interpolations.

    That ``:`` arrives as a 1-character ``FSTRING_MIDDLE`` token and
    must not trigger the dict-colon spacing rule.
    """
    src = 'x = f"{a}:{b}"\n'
    assert format_source(src) == src


def test_inline_comment_after_opener_keeps_padding():
    """Inline trailing comment after ``(`` must keep its 2-space gap,
    not get glued by the no-space-after-opener rule."""
    src = "f(  # opener comment\n    x,\n)\n"
    out = format_source(src)
    assert "(  # opener comment" in out


def test_inline_comment_after_dollar_capture_in_string():
    """Regression: xonsh's tokenizer can emit a ``COMMENT`` token whose
    value carries a stray leading space when a ``$(...)`` capture
    appeared earlier inside a string literal. The formatter must not
    double-count that into the inter-token padding."""
    src = '''script = """
$(echo)
"""
@deco(x=1)  # comment
def f():
    pass
'''
    out = format_source(src)
    # Exactly two spaces (PEP 8 inline-comment padding), not three.
    assert "@deco(x=1)  # comment" in out
    assert "@deco(x=1)   # comment" not in out


def test_triple_quoted_fstring_with_brace_escapes_preserved():
    # Multi-line triple-quoted f-strings with literal-brace escapes
    # must not lose content. The xonsh tokenizer reports bogus end
    # positions for these tokens, so the formatter relies on a
    # fallback that re-escapes braces on the decoded value.
    src = 'WIZARD = f"""\n  {{TITLE}} hi {name}\n  {{END}}\n"""\n'
    out = format_source(src)
    # Content (including {{TITLE}} and {{END}}) must survive round-trip.
    assert "{{TITLE}}" in out
    assert "{{END}}" in out
    assert "hi {name}" in out
    # And the result must remain a valid f-string (re-tokenize cleanly).
    from xonsh.formatter.core import _Formatter

    _Formatter(out).run()  # raises FormatError if it became unparseable


# ---------------------------------------------------------------------
# Idempotence — `format(format(x)) == format(x)`
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "x = 1\n",
        "x=1\n",
        "def f(a,b=1):\n    return a+b\n",
        "class Foo:\n    def m(self):\n        pass\n# tail\n",
        "echo ${HOME} && !(grep py)\n",
        "for f in g`*.py`:\n    print(f)\n",
        "x = $(ls)\n",
        "#hello\nx = 1\n",
        "if x:\n    if y:\n        z = 1\n",
        "lambda x=1: x + 1\n",
    ],
)
def test_idempotent(src):
    once = format_source(src)
    twice = format_source(once)
    assert once == twice


# ---------------------------------------------------------------------
# Token-stream invariance — the structural token sequence must be
# preserved across formatting (the only changes happen in whitespace
# tokens). This is the closest equivalent of "AST round-trip" for a
# token-based formatter.
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "x = 1\n",
        "x=1\n",
        "def f(a, b=1):\n    return a + b\n",
        "x = $(ls -la)\n",
        "echo ${HOME} && !(grep py)\n",
        "for f in g`*.py`:\n    print(f)\n",
        "class C:\n    def m(self):\n        pass\n# tail\n",
        "if x: y = 1\n",
        "lambda x=1: x\n",
    ],
)
def test_token_stream_invariant(src):
    """Formatting must not alter the meaningful token sequence."""
    assert _token_skeleton(src) == _token_skeleton(format_source(src))


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


def test_format_error_on_eof_in_paren():
    with pytest.raises(FormatError):
        format_source("x = (1 + \n")


def test_format_error_on_eof_in_triple_quoted_string():
    with pytest.raises(FormatError):
        format_source('x = """unterminated\n')
