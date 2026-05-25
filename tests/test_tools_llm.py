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
"""

import pytest

from xonsh.parsers.lexer import Lexer
from xonsh.tools import strip_continuation_comments, subproc_toks

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
