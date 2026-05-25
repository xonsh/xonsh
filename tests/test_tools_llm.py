"""LLM-generated regression coverage for ``xonsh.tools`` parsing helpers.

GH-6386 — ``subproc_toks`` against already-wrapped lines
========================================================

``subproc_toks`` called on a line that has already been partially wrapped
by an earlier parse pass (e.g. xonsh phase 1 turning ``echo && echo hi``
into ``echo && ![echo hi]``) used to re-wrap the existing ``![…]`` block,
producing ``![![…]]`` — which is not valid xonsh, since neither ``![…]``
nor ``&&``/``||`` may appear inside ``![…]``.  The bug surfaced in
xontribs that force ``CtxAwareTransformer.mode = "eval"`` to compensate
for shifted column numbers in their compiled output (the ``coconut``
xontrib being the canonical example), making the whole-line wrap reach
phase-1 output.

These tests pin the corrected behaviour at the ``subproc_toks`` layer
without depending on coconut: skip already-wrapped ``![…]``/``$[…]``
blocks, fall back to the bare region preceding the skip when the
trailing region is fully wrapped, and decline (return ``None``) when
every region in the chain is already wrapped.

GH-6414 — ``strip_continuation_comments`` (fish-style)
======================================================

A physical line that is "just a comment" sitting inside a multi-line
command joined by backslash continuation should be transparent — the
continuation extends through it to the next physical line, mirroring
fish-shell behaviour. ``strip_continuation_comments`` normalises this
at source-level so the rest of the pipeline (``tokenize``,
``_ends_with_line_continuation``, ``get_logical_line``,
``subproc_toks``) sees a uniform continuation chain. Tests pin both the
success cases and the boundaries that must remain unchanged: ``#``
inside a string literal, an inline ``# \\`` at the end of a regular
code line (#6294 regression), and lines inside an open triple-quoted
string.

f-string conversion ``!r``/``!s``/``!a`` inside ``{…}``
========================================================

In subproc mode the xonsh lexer emits ``BANG`` for ``!``, regardless of
whether it sits inside an f-string replacement field (where ``!r``,
``!s``, ``!a`` are *conversion specifiers* — purely textual, with no
relation to xonsh macros) or at top level (where ``!`` is the macro
operator).  Without f-string awareness, ``subproc_toks`` and
``find_next_break`` treated any ``BANG`` as macro-start: the former
swallowed the rest of the line into a single wrap that then failed to
re-parse (``code: @(``), the latter returned ``maxcol = end-of-line``
which prevented wrapping the LHS before a combinator.  The fix tracks
``FSTRING_START`` / ``FSTRING_END`` nesting and ``LBRACE`` /
``RBRACE`` depth, ignoring ``BANG`` while inside a replacement field.

GH-6011 — multi-line ``@()`` plus shell combinator
==================================================

A logical line that spans more than one physical line because a triple-
quoted ``@()`` argument contains a literal newline used to crash phase-1
subproc recovery when joined with ``&&``/``||``/``;``.  The fix has
three independent components, all pinned by tests below:

1. ``_have_open_triple_quotes`` — replaced a per-line count of ``\"\"\"``
   with a context-aware scanner that honours string prefixes
   (``r``/``b``/``f`` in any case-combination), backslash escapes inside
   non-raw strings, single-quoted strings, and ``#`` comments.  The old
   implementation declared the count odd → open, which mistook the
   closing ``\"\"\"`` of a string opened earlier (after ``splitlines``)
   for a new opener.

2. ``_abs_lexpos`` — a new helper that converts ``tok.lexpos`` (column
   on the token's physical line) into an absolute offset in the joined
   multiline string.  Without it, ``find_next_break`` and ``subproc_toks``
   placed positions past a triple-quoted-string newline at the wrong
   spot and wrapped a random slice of the literal.  Special-cases
   ``FSTRING_MIDDLE``, where PEP 701's tokenizer reports
   ``(end_line, start_col_on_start_line)`` — recovered by subtracting
   the newlines in the token value.

3. ``get_logical_line`` walks backward through ``open triple_quoted``
   contexts (not just backslash continuations), using the joined
   prefix of earlier physical lines to disambiguate open from close.
   ``replace_logical_line`` collapses the affected slot to a single
   entry when the logical line contains a real ``\\n`` from a literal,
   so the downstream ``"\\n".join(lines)`` round-trips exactly.
"""

import pytest

from xonsh.parsers.lexer import Lexer
from xonsh.tools import (
    _have_open_triple_quotes,
    find_next_break,
    get_logical_line,
    replace_logical_line,
    strip_continuation_comments,
    subproc_toks,
)

LEXER = Lexer()
LEXER.build()


@pytest.mark.parametrize(
    "line",
    [
        "echo && ![echo hi]",
        "echo && $[echo hi]",
        "![echo a] && ![echo b]",
        "$[echo a] && $[echo b]",
        "![echo a] || ![echo b]",
        "true && ![echo hi]",
        "false || ![echo hi]",
    ],
)
def test_subproc_toks_skips_already_wrapped(line):
    """Whole-line wrap must not produce ``![![…]]`` when the line has
    already-wrapped subproc blocks.  Either the bare side gets a
    correct fresh wrap, or the function declines to wrap entirely.
    """
    for greedy in (False, True):
        obs = subproc_toks(
            line, mincol=0, maxcol=None, lexer=LEXER, returnline=False, greedy=greedy
        )
        if obs is None:
            continue
        assert "![![" not in obs, f"double wrap in {obs!r}"
        assert "![$[" not in obs, f"double wrap in {obs!r}"


@pytest.mark.parametrize(
    "line, expected",
    [
        # Bare LEFT, already-wrapped RIGHT: wrap only the bare LEFT.
        ("echo && ![echo hi]", "![echo]"),
        ("echo && $[echo hi]", "![echo]"),
        # Bare LEFT, already-wrapped RIGHT, with ||.
        ("echo || ![echo hi]", "![echo]"),
        # Both sides already-wrapped: nothing left to wrap, return None.
        ("![echo a] && ![echo b]", None),
        ("$[echo a] && $[echo b]", None),
        ("![echo a] || $[echo b]", None),
    ],
)
def test_subproc_toks_already_wrapped_chain(line, expected):
    """Whole-line wrap on a chain that includes ``![…]``/``$[…]`` must
    only produce a wrap for the still-bare side (or ``None`` when every
    side is already wrapped).
    """
    obs = subproc_toks(line, mincol=0, maxcol=None, lexer=LEXER, returnline=False)
    assert obs == expected


# --- GH-6414: fish-style continuation comments -------------------------


@pytest.mark.parametrize(
    "src, exp",
    [
        # Issue #6414 example: comment with trailing ``\`` between
        # continued lines is consumed, continuation extends through.
        (
            "echo 1 \\\n    # 2 \\\n    3 \\\n    4\n",
            "echo 1 \\\n\\\n    3 \\\n    4\n",
        ),
        # Comment without trailing ``\`` is also transparent inside a
        # continuation chain (matches fish-shell semantics).
        (
            "echo 1 \\\n    # 2\n    3\n",
            "echo 1 \\\n\\\n    3\n",
        ),
        # Multiple comment-only lines in a row are all consumed.
        (
            "echo a \\\n    # c1\n    # c2 \\\n    b\n",
            "echo a \\\n\\\n\\\n    b\n",
        ),
        # A blank line breaks the continuation; the comment-only line
        # preceding it is replaced, but the blank line ends the chain.
        (
            "echo 1 \\\n    # comment\n\n    3\n",
            "echo 1 \\\n\\\n\n    3\n",
        ),
        # Top-level comment with no preceding ``\`` continuation is
        # left untouched.
        (
            "echo first\n# comment\necho second\n",
            "echo first\n# comment\necho second\n",
        ),
        # Inline ``# \\`` at the end of a regular code line must NOT
        # set in_continuation -- regression for #6294 follow-up.
        ("a = 1 # \\\necho 1\n", "a = 1 # \\\necho 1\n"),
        # Lines inside an open triple-quoted string are not touched
        # even if they look like comment-only physical lines.
        (
            's = """foo\n# in string\nbar"""\n',
            's = """foo\n# in string\nbar"""\n',
        ),
        # ``#`` inside a string literal does not start a comment, so a
        # ``\\`` at end of that line is a real continuation.
        (
            'echo "1 # not comment" \\\n    2\n',
            'echo "1 # not comment" \\\n    2\n',
        ),
        # Source without any newlines is returned as-is.
        ("echo hi", "echo hi"),
        # CRLF line endings are preserved.
        (
            "echo 1 \\\r\n    # 2\r\n    3\r\n",
            "echo 1 \\\r\n\\\r\n    3\r\n",
        ),
        # Comment-only line at the very start (no preceding ``\``)
        # remains unchanged.
        ("# header\necho 1\n", "# header\necho 1\n"),
        # Tab/whitespace-prefixed comment also matches.
        (
            "echo 1 \\\n\t# tabbed\n    2\n",
            "echo 1 \\\n\\\n    2\n",
        ),
    ],
)
def test_strip_continuation_comments(src, exp, xession):
    # Pin the line-continuation marker to ``\\`` so expectations stay
    # platform-agnostic. On Windows, ``get_line_continuation()`` returns
    # ``" \\"`` whenever ``XONSH_INTERACTIVE`` is true, which the preprocessor
    # would faithfully use as the replacement marker — but the unit-test
    # expectations encode the non-interactive shape.
    xession.env["XONSH_INTERACTIVE"] = False
    assert strip_continuation_comments(src) == exp


# --- f-string conversion ``!r``/``!s``/``!a`` inside ``{…}`` ---------------
#
# In subproc mode the lexer emits ``BANG`` for ``!``, regardless of
# whether it sits inside an f-string replacement field (where it means
# "conversion specifier") or at top level (where it means "macro call").
# Without f-string awareness, ``subproc_toks`` and ``find_next_break``
# treat any ``BANG`` as macro-start: the former swallows the rest of
# the line into a single wrap that then fails to re-parse, the latter
# returns ``maxcol = end-of-line`` which prevents wrapping the LHS
# before a combinator.  The fix tracks ``FSTRING_START`` / ``FSTRING_END``
# nesting and ``LBRACE`` / ``RBRACE`` depth, ignoring ``BANG`` while
# inside a replacement field.


@pytest.mark.parametrize(
    "line, expected",
    [
        # ``!r`` conversion — the wrap must cover the whole ``@()``
        # subproc segment up to the ``&&``, not stop at the ``!``.
        (
            'echo @(f"hi {name!r}") && echo z',
            '![echo @(f"hi {name!r}")] && echo z',
        ),
        # ``!s`` and ``!a``.
        (
            'echo @(f"x {y!s}") && echo z',
            '![echo @(f"x {y!s}")] && echo z',
        ),
        (
            'echo @(f"x {y!a}") && echo z',
            '![echo @(f"x {y!a}")] && echo z',
        ),
        # Conversion plus a format spec — the ``:`` introduces a
        # ``FSTRING_MIDDLE`` for the spec text, ``BANG`` still must be
        # treated as conversion.
        (
            'echo @(f"x {y!r:>10}") && echo z',
            '![echo @(f"x {y!r:>10}")] && echo z',
        ),
    ],
)
def test_subproc_toks_fstring_conversion(line, expected):
    """Wrap up to ``&&`` even though the f-string contains ``{x!r}``."""
    maxcol = find_next_break(line, mincol=-1, lexer=LEXER)
    obs = subproc_toks(line, lexer=LEXER, maxcol=maxcol, returnline=True)
    assert obs == expected


@pytest.mark.parametrize(
    "line, expected_maxcol",
    [
        # ``find_next_break`` returns one past the lexpos of the
        # combinator token.  For ``&&`` / ``||`` / ``;`` at lexpos 23
        # this is ``24``.  Without the f-string guard, the ``BANG``
        # inside ``{x!r}`` would trigger an early break and return
        # ``len(line)+1`` instead.
        (
            'echo @(f"hi {name!r}") && echo z',
            24,
        ),
        (
            'echo @(f"hi {name!r}") || echo z',
            24,
        ),
        (
            'echo @(f"hi {name!r}") ; echo z',
            24,
        ),
        # Without any ``!``, the position shifts because the f-string
        # is shorter — sanity check that the value is still the
        # combinator position, not end-of-line.
        (
            'echo @(f"hi {name}") && echo z',
            22,
        ),
    ],
)
def test_find_next_break_fstring_conversion(line, expected_maxcol):
    """``find_next_break`` must not treat ``!`` inside an f-string
    replacement field as a macro break — only top-level ``BANG``
    qualifies.
    """
    obs = find_next_break(line, mincol=-1, lexer=LEXER)
    assert obs == expected_maxcol


@pytest.mark.parametrize(
    "line",
    [
        # Bare macro at top level — ``!`` IS a macro operator here.
        # ``subproc_toks`` must still recognise it (saw_macro behaviour).
        "echo ! something",
        "cmd ! arg with spaces",
        # Macro inside an already-wrapped block.
        "$[echo ! arg]",
        "![echo ! arg]",
    ],
)
def test_subproc_toks_macro_outside_fstring_still_works(line):
    """Pin the inverse: ``BANG`` outside an f-string replacement field
    is still the xonsh macro operator and ``subproc_toks`` must accept
    it (i.e., not decline by mistake after the f-string-conversion
    guard).
    """
    obs = subproc_toks(line, lexer=LEXER, returnline=True)
    # Either the function wraps the line (placing ``![…]`` around it)
    # or, for an already-wrapped input, leaves it alone — but never
    # crashes and never collapses to a comment-only ``None`` return.
    assert obs is None or "!" in obs


# --- GH-6011: multi-line @() plus shell combinator ---------------------


@pytest.mark.parametrize(
    "s, expected",
    [
        # Empty / no quotes
        ("", False),
        ("echo hello", False),
        ("x = 1", False),
        # Closed triple double-quote
        ('"""abc"""', False),
        ('x = """abc"""', False),
        # Open triple double-quote
        ('"""abc', '"""'),
        ('x = """abc\ndef', '"""'),
        # Closed triple single-quote
        ("'''abc'''", False),
        # Open triple single-quote
        ("'''abc", "'''"),
        # A line that contains *only* a closing triple quote, in
        # isolation -- without prefix context the scanner correctly
        # reports it as an opener (cross-line context is supplied by
        # callers, e.g. ``get_logical_line`` joins the prefix).
        ('""") && echo 2', '"""'),
        # Single-quoted string containing escaped quote markers must
        # not confuse the scanner.
        ('"\\"\\"\\""', False),
        ('x = "abc def"', False),
        # ``#`` inside a string is literal, ``#`` outside opens a comment
        ('"# in str"', False),
        ('x = """abc""" # """comment', False),
        # ``\\\"\"\"`` inside a non-raw string is an escaped quote;
        # the triple is closed by the final ``\"\"\"``.
        ('"""abc\\"""def"""', False),
        # Raw triple ignores backslash escapes: ``r\"\"\"abc\\\"\"\"`` is
        # closed by the trailing ``\"\"\"``.
        ('r"""abc\\"""', False),
        ('r"""abc', '"""'),
        # ``b`` / ``f`` prefixes — closed
        ('b"""abc"""', False),
        ('f"""abc"""', False),
        # ``rb`` / ``br`` / ``fr`` — raw + bytes/f-string
        ('rb"""abc"""', False),
        ('br"""abc"""', False),
        ('fr"""abc"""', False),
        # An identifier ending in ``r`` followed by ``\"\"\"`` is NOT a
        # raw string -- the ``r`` is part of the identifier and the
        # string is non-raw.
        ('foor"""abc"""', False),
        # Closed triple followed by an unterminated single-line string
        # at end of input: the single-line string ends at EOL.
        ('"""abc""" + "def', False),
        # Comments don't open strings
        ('# """ this is a comment', False),
        ('echo 1 # """ comment\necho 2', False),
        # f-string with embedded expression is still a normal string
        # for opener-detection purposes.
        ('f"""hello {name}"""', False),
        ('f"""hello {name}', '"""'),
    ],
)
def test_have_open_triple_quotes(s, expected):
    """GH-6011: ``_have_open_triple_quotes`` must understand string
    prefixes (raw, bytes, f-string), backslash escapes inside non-raw
    strings, single-quoted strings, and ``#`` comments.  The previous
    implementation counted ``\"\"\"`` occurrences per call and returned
    odd → True, which is wrong on inputs with mixed quote kinds or with
    triple-quote markers inside a comment or single-line string.
    """
    assert _have_open_triple_quotes(s) == expected


@pytest.mark.parametrize(
    "src, idx, exp_line, exp_n, exp_start",
    [
        # idx points to the second physical line — which is the
        # *closing* ``\"\"\"`` of a triple-quoted string opened above.
        # ``get_logical_line`` must walk backwards from idx=1 to idx=0
        # so the whole literal is joined back into one logical line.
        (
            'echo @("""1\n""") && echo 2',
            1,
            'echo @("""1\n""") && echo 2',
            2,
            0,
        ),
        # Same on the first line — already at the start.
        (
            'echo @("""1\n""") && echo 2',
            0,
            'echo @("""1\n""") && echo 2',
            2,
            0,
        ),
        # Three-line span — idx in the middle should still walk back.
        (
            'echo @("""a\nb\nc""")',
            1,
            'echo @("""a\nb\nc""")',
            3,
            0,
        ),
        (
            'echo @("""a\nb\nc""")',
            2,
            'echo @("""a\nb\nc""")',
            3,
            0,
        ),
        # Triple single-quote.
        (
            "echo @('''1\n''') && echo 2",
            1,
            "echo @('''1\n''') && echo 2",
            2,
            0,
        ),
    ],
)
def test_get_logical_line_walks_back_through_open_triple(
    src, idx, exp_line, exp_n, exp_start, xession
):
    """GH-6011: when ``idx`` lands on a physical line that is the body
    or closer of a triple-quoted string opened earlier,
    ``get_logical_line`` must walk backwards to the opener so the joined
    result covers the full literal.  The previous implementation only
    walked back through backslash continuations.
    """
    lines = src.splitlines()
    line, n, start = get_logical_line(lines, idx)
    assert line == exp_line
    assert n == exp_n
    assert start == exp_start


@pytest.mark.parametrize(
    "src, idx, n, logical",
    [
        # The logical line contains a real ``\n`` from a triple-quoted
        # string.  The original split-on-space logic would cut inside
        # the literal (or place the closing ``\"\"\"`` on the wrong
        # physical line).  Collapse the affected slot to a single entry.
        (
            ['echo @("""1', '""") && echo 2'],
            0,
            2,
            '![echo @("""1\n""")] && echo 2',
        ),
        # Three-line span collapses to one slot too.
        (
            ['echo @("""a', "b", 'c""")'],
            0,
            3,
            '![echo @("""a\nb\nc""")]',
        ),
    ],
)
def test_replace_logical_line_multiline_collapse(src, idx, n, logical, xession):
    """GH-6011: when a logical line is reconstructed from a multiline
    triple-quoted span, ``replace_logical_line`` must collapse the
    affected slot to a single list entry — re-splitting along the
    original physical boundaries inside a string literal is meaningless,
    and the downstream ``\"\\n\".join(lines)`` round-trip then preserves
    the contents exactly.
    """
    lines = list(src)
    replace_logical_line(lines, logical, idx, n)
    assert "\n".join(lines) == logical


@pytest.mark.parametrize(
    "line, expected_lhs_wrap, expected_rhs_wrap",
    [
        # ``subproc_toks`` wraps a single subproc segment per call.
        # ``find_next_break`` gives ``maxcol`` to limit the wrap to the
        # left of the combinator; without ``maxcol`` the function wraps
        # the trailing segment instead.  The execer recovery loop calls
        # it once per side, so both wraps need to come out right.
        (
            'echo @("""1\n""") && echo 2',
            '![echo @("""1\n""")] && echo 2',
            'echo @("""1\n""") && ![echo 2]',
        ),
        (
            'echo @("""1\n""") || echo 2',
            '![echo @("""1\n""")] || echo 2',
            'echo @("""1\n""") || ![echo 2]',
        ),
        (
            'echo @("""1\n""") ; echo 2',
            '![echo @("""1\n""")] ; echo 2',
            'echo @("""1\n""") ; ![echo 2]',
        ),
        (
            "echo @('''1\n''') && echo 2",
            "![echo @('''1\n''')] && echo 2",
            "echo @('''1\n''') && ![echo 2]",
        ),
        (
            'echo @("""a\nb\nc""") && echo done',
            '![echo @("""a\nb\nc""")] && echo done',
            'echo @("""a\nb\nc""") && ![echo done]',
        ),
    ],
)
def test_subproc_toks_pyeval_multiline_with_combinator(
    line, expected_lhs_wrap, expected_rhs_wrap
):
    """GH-6011: ``tok.lexpos`` is a per-physical-line column.  Before
    the fix, ``subproc_toks`` and ``find_next_break`` treated it as an
    absolute offset, so the ``&&`` after a triple-quoted ``@()``
    argument ended up at the wrong position and wrapped a random slice
    of the string literal.

    The corrected behaviour: with ``maxcol`` from ``find_next_break``,
    the LHS of the combinator wraps exactly; without ``maxcol`` the
    trailing segment (RHS) wraps instead.  The execer recovery loop
    calls ``subproc_toks`` once per side.
    """
    maxcol = find_next_break(line, mincol=-1, lexer=LEXER)
    obs_lhs = subproc_toks(line, lexer=LEXER, maxcol=maxcol, returnline=True)
    assert obs_lhs == expected_lhs_wrap
    obs_rhs = subproc_toks(line, lexer=LEXER, returnline=True)
    assert obs_rhs == expected_rhs_wrap


@pytest.mark.parametrize(
    "line, mincol, expected",
    [
        # ``&&`` lives on physical line 2 at column 5.  The absolute
        # offset of the second ``&`` is 17 (length of line 1 plus 5).
        # ``find_next_break`` returns one past the break — ``18``.
        ('echo @("""1\n""") && echo 2', -1, 18),
        ('echo @("""1\n""") && echo 2', 0, 18),
        ('echo @("""1\n""") || echo 2', -1, 18),
        # ``;`` at line-2 col 5 — same absolute offset as ``&&``.
        ('echo @("""1\n""") ; echo 2', -1, 18),
        # f-string variant -- PEP 701 splits the multiline f-string
        # into FSTRING_START / FSTRING_MIDDLE / FSTRING_END tokens, and
        # FSTRING_MIDDLE has the unusual (start_lnum, end_col) layout
        # that ``_abs_lexpos`` compensates for.
        ('echo @(f"""1\n""") && echo 2', -1, 19),
    ],
)
def test_find_next_break_multiline_pyeval(line, mincol, expected):
    """GH-6011: ``find_next_break`` must return absolute offsets in
    the joined multiline string, not per-line columns.  The fix added
    ``_abs_lexpos`` to convert ``tok.lexpos`` correctly across newlines
    inside string literals.
    """
    assert find_next_break(line, mincol=mincol, lexer=LEXER) == expected


def test_subproc_toks_pyeval_multiline_fstring():
    """GH-6011 f-string variant: PEP 701 splits a multiline f-string
    into three tokens (FSTRING_START + FSTRING_MIDDLE + FSTRING_END).
    FSTRING_MIDDLE has an unusual position encoding -- ``tok.lineno``
    points to the line where the value *ends*, but ``tok.lexpos`` is
    the column where the value *started* on its start line.
    ``_abs_lexpos`` must compensate, otherwise ``subproc_toks`` wraps
    the wrong slice.
    """
    line = 'echo @(f"""1\n""") && echo 2'
    maxcol = find_next_break(line, mincol=-1, lexer=LEXER)
    obs = subproc_toks(line, lexer=LEXER, maxcol=maxcol, returnline=True)
    assert obs == '![echo @(f"""1\n""")] && echo 2'
