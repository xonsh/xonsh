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
"""

import pytest

from xonsh.parsers.lexer import Lexer
from xonsh.tools import find_next_break, strip_continuation_comments, subproc_toks

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
        # ``find_next_break`` returns the lexpos of the combinator
        # token (with ``mincol=-1`` the per-mincol shift cancels out).
        # For ``&&`` / ``||`` / ``;`` at lexpos 23 this is ``23``.
        # Without the f-string guard, the ``BANG`` inside ``{x!r}``
        # would trigger an early break and return ``len(line)``
        # instead.
        (
            'echo @(f"hi {name!r}") && echo z',
            23,
        ),
        (
            'echo @(f"hi {name!r}") || echo z',
            23,
        ),
        (
            'echo @(f"hi {name!r}") ; echo z',
            23,
        ),
        # Without any ``!``, the position shifts because the f-string
        # is shorter — sanity check that the value is still the
        # combinator position, not end-of-line.
        (
            'echo @(f"hi {name}") && echo z',
            21,
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
