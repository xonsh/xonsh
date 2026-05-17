"""LLM-generated end-to-end regression tests for the execer.

GH-6386 — ``CtxAwareTransformer.try_subproc_toks`` in eval mode
===============================================================

With the ``coconut`` xontrib loaded, ``CtxAwareTransformer.mode`` is
forced to ``"eval"`` so the whole stripped logical line is fed to
``subproc_toks``.  When phase 1 has already wrapped part of the line as
``![…]`` (e.g. for ``echo && echo hi`` → ``echo && ![echo hi]``), the
eval-mode wrap of the remaining bare ``Name`` used to produce
``![![echo hi]]`` (invalid xonsh), the parser raised ``SyntaxError``,
``try_subproc_toks`` swallowed it, and the bare ``Name('echo')``
survived to runtime as a ``NameError``.  A second variant silently
miscompiled ``cmd1 && cmd2`` (both bare, both single-token) into
``cmd2 && cmd2``.

The tests reproduce both classes without depending on coconut by
driving ``CtxAwareTransformer`` in eval mode directly via the same
``mode = "eval"`` flip the coconut xontrib performs (see
``coconut.integrations.CoconutXontribLoader.new_try_subproc_toks``).

GH-6414 — fish-style continuation comments
==========================================

A multi-line command joined with backslash continuation may contain
comment-only lines in between; the continuation extends through them.
These tests drive the public ``Execer.parse`` path so they exercise
both the source preprocessor (``strip_continuation_comments``) and
every downstream consumer that depends on a coherent continuation
chain — ``tokenize``, ``_ends_with_line_continuation``,
``get_logical_line``, ``subproc_toks``, and the context-aware
transformer's recovery loop.  Without the preprocessor these snippets
either fail to parse outright (``SyntaxError: unexpected indent``) or
hit the recovery loop's safety bail-out as the comment-only line
repeatedly breaks the logical line.
"""

import ast as pyast

import pytest


@pytest.mark.parametrize(
    "line",
    [
        "echo && echo hi",
        "echo hi && echo",
        "echo a && echo b",
        "ls && pwd",
        "pwd && ls",
        "ls && pwd /",
        "echo a && pwd b",
        "true && false || echo hi",
        "false || echo hi",
        "(echo) && (echo hi)",
        "echo && echo",
    ],
)
def test_andor_chain_eval_mode(line, xession):
    """Phase-2 eval-mode wrap must produce the same AST as exec-mode for
    plain xonsh subproc chains.  Coconut forces eval-mode for every
    call to ``try_subproc_toks``; without the GH-6386 fix the bare
    ``Name`` on the left of ``&&``/``||`` is left untransformed (loud
    ``NameError``) or silently replaced with the wrong subproc wrap
    (silent miscompile).
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    src = line + "\n"
    exec_tree = execer.parse(src, ctx=ctx, mode="single")
    exec_unparsed = pyast.unparse(exec_tree)
    # Drive eval-mode the way the coconut xontrib does: temporarily flip
    # ``ctxtransformer.mode`` to ``"eval"`` for every ``try_subproc_toks``
    # call.  This mirrors ``CoconutXontribLoader.new_try_subproc_toks``.
    ctxt = execer.ctxtransformer
    orig_try_subproc_toks = ctxt.try_subproc_toks

    def eval_mode_try_subproc_toks(node, strip_expr=False):
        prev = ctxt.mode
        ctxt.mode = "eval"
        try:
            return orig_try_subproc_toks(node, strip_expr=strip_expr)
        finally:
            ctxt.mode = prev

    ctxt.try_subproc_toks = eval_mode_try_subproc_toks
    try:
        eval_tree = execer.parse(src, ctx=ctx, mode="single")
    finally:
        ctxt.try_subproc_toks = orig_try_subproc_toks
    eval_unparsed = pyast.unparse(eval_tree)
    assert eval_unparsed == exec_unparsed, (
        f"eval-mode wrap diverged from exec-mode wrap for {line!r}\n"
        f"  exec: {exec_unparsed}\n"
        f"  eval: {eval_unparsed}"
    )


# --- GH-6011: multiline @("""…""") with && --------------------------------


def test_multiline_atlparen_triple_string_and_chain(xession):
    """Phase-1 recovery must wrap both sides of ``&&`` on a logical line that
    contains a multiline triple-quoted ``@()`` argument (issue #6011).
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    src = (
        'echo @("""1\n'
        '                                                             """) && echo 2\n'
    )
    tree = execer.parse(src, ctx=ctx, mode="single")
    assert tree.body, "expected a non-empty AST"
    unparsed = pyast.unparse(tree.body[0])
    assert "BoolOp" in unparsed or "and" in unparsed.lower()
    assert "subproc" in unparsed


# --- GH-6414: fish-style continuation comments -------------------------


@pytest.mark.parametrize(
    "code",
    [
        # Issue #6414: original example
        "echo 1 \\\n    # 2 \\\n    3 \\\n    4\n",
        # Comment with no trailing backslash is also transparent
        "echo 1 \\\n    # 2\n    3\n",
        # Multiple consecutive comment-only lines
        "echo a \\\n    # c1\n    # c2 \\\n    b\n",
        # Mixed: one comment with `\\`, one without
        "echo a \\\n    # c1 \\\n    # c2\n    b\n",
        # Inside a function body
        "def f():\n    echo 1 \\\n        # inner comment\n        2\nf()\n",
        # Inside a $() substitution
        "x = $(echo 1 \\\n    # 2 \\\n    3)\n",
    ],
)
def test_line_cont_with_comment(code, xonsh_execer_parse):
    assert xonsh_execer_parse(code)
