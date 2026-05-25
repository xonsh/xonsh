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


# --- f-string conversion (``{x!r}``/``{x!s}``/``{x!a}``) -----------------
#
# In subproc mode the xonsh lexer emits ``BANG`` for ``!``.  Without
# f-string awareness, ``subproc_toks`` and ``find_next_break`` treat
# any ``BANG`` as the start of a macro call, swallowing the rest of
# the line into a single ``![…]`` wrap that then fails to re-parse
# (``code: @(``).  ``f"{name!r}"`` and friends use ``!`` as a
# *conversion specifier* — purely textual, with no relation to xonsh
# macros — so the fix tracks f-string nesting (``FSTRING_START`` /
# ``FSTRING_END``) and replacement-field depth (``LBRACE`` /
# ``RBRACE``) and ignores ``BANG`` while ``fstring_expr_depth > 0``.


@pytest.mark.parametrize(
    "src",
    [
        # Plain ``!r`` conversion in ``@()`` followed by ``&&``.
        'echo @(f"hi {name!r}") && echo z\n',
        # ``!s`` and ``!a`` are the other two conversions.
        'echo @(f"x {y!s}") && echo z\n',
        'echo @(f"x {y!a}") && echo z\n',
        # Triple-quoted f-string with conversion.
        'echo @(f"""hi {name!r}""") && echo z\n',
        # Conversion + format spec (``:>10``).
        'echo @(f"x {y!r:>10}") && echo z\n',
        # PEP 701 nested f-string with conversion in the inner one.
        'echo @(f"""a {f"{x!r}"} b""") && echo z\n',
        # Plain Python statement with conversion — should never have
        # touched recovery, but covers the path nonetheless.
        'x = "world"\nprint(f"hi {x!r}")\n',
    ],
)
def test_fstring_conversion_in_pyeval(src, xession):
    """f-string conversion (``{x!r}``/``{x!s}``/``{x!a}``) inside an
    ``@()`` argument used to break recovery because the subproc-mode
    lexer reported the ``!`` as a ``BANG`` token, which
    ``subproc_toks`` / ``find_next_break`` interpreted as the start of
    a macro call.  The fix tracks f-string nesting and ignores
    ``BANG`` while inside a replacement field.
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    tree = execer.parse(src, ctx=ctx, mode="exec")
    assert tree is not None
    assert tree.body, f"expected non-empty AST for {src!r}"


@pytest.mark.parametrize(
    "src",
    [
        # Bare macro at top level still wraps; the ``!`` is outside any
        # f-string.  These are existing baselines pinned for regression.
        "$[echo ! arg]\n",
        "![echo ! arg]\n",
        "$(echo ! arg)\n",
        "!(echo ! arg)\n",
        # Macro with multi-line triple-quoted argument.
        '![echo ! """a\nb"""]\n',
    ],
)
def test_macro_still_works_after_fstring_fix(src, xession):
    """Pin the macro-call paths: the f-string-conversion guard only
    suppresses ``BANG``-as-macro detection while ``fstring_expr_depth
    > 0``.  Top-level macros (and macros inside ``$[…]``/``![…]``)
    must continue to be recognised.
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    tree = execer.parse(src, ctx=ctx, mode="exec")
    assert tree is not None
    assert tree.body, f"expected non-empty AST for {src!r}"
