"""Tests for ``xonsh.tools.subproc_toks`` against already-wrapped lines.

Regression coverage for GH-6386: ``subproc_toks`` called on a line that
has already been partially wrapped by an earlier parse pass (e.g. xonsh
phase 1 turning ``echo && echo hi`` into ``echo && ![echo hi]``) used
to re-wrap the existing ``![…]`` block, producing ``![![…]]`` — which
is not valid xonsh, since neither ``![…]`` nor ``&&``/``||`` may appear
inside ``![…]``.  The bug surfaced in xontribs that force
``CtxAwareTransformer.mode = "eval"`` to compensate for shifted column
numbers in their compiled output (the ``coconut`` xontrib being the
canonical example), making the whole-line wrap reach phase-1 output.

These tests pin the corrected behaviour at the ``subproc_toks`` layer
without depending on coconut: skip already-wrapped ``![…]``/``$[…]``
blocks, fall back to the bare region preceding the skip when the
trailing region is fully wrapped, and decline (return ``None``) when
every region in the chain is already wrapped.
"""

import pytest

from xonsh.parsers.lexer import Lexer
from xonsh.tools import subproc_toks

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
