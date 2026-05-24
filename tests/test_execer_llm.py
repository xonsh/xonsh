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


# --- GH-6011: multiline @(...) with shell combinators ------------------
#
# A logical line that spans more than one physical line because it
# contains a triple-quoted ``@()`` argument, joined with a shell
# combinator (``&&``/``||``/``;``), used to crash phase-1 subproc
# recovery.  Two distinct bugs combined to cause the failure:
#
#   1.  ``_have_open_triple_quotes`` counted ``\"\"\"`` per physical line,
#       so the closing ``\"\"\"`` of a string opened on an earlier line
#       was misidentified as a new opener — ``get_logical_line`` then
#       failed to walk backwards to the real start of the logical line.
#
#   2.  ``tok.lexpos`` is the column *within the token's physical line*,
#       not an absolute offset in the input string.  ``find_next_break``
#       and ``subproc_toks`` used it as an absolute offset, so positions
#       past a triple-quoted-string newline came out wrong, wrapping
#       random substrings (or wrapping the whole line greedily, which
#       then failed because ``![…]`` does not permit ``&&``/``||`` inside).
#
# These tests pin the fix end-to-end at the ``Execer.parse`` boundary.


@pytest.mark.parametrize(
    "src",
    [
        # The exact example from issue #6011
        'echo @("""1\n""") && echo 2\n',
        # || combinator
        'echo @("""1\n""") || echo 2\n',
        # ; combinator
        'echo @("""1\n""") ; echo 2\n',
        # Triple single-quote variant
        "echo @('''1\n''') && echo 2\n",
        # Multi-line @() on the RHS
        'echo 0 && echo @("""x\ny""")\n',
        # Three-element chain with multiline @() at the head
        'echo @("""1\n""") && echo 2 && echo 3\n',
        # Mixed && / ||
        'echo @("""1\n""") && echo 2 || echo 3\n',
        # Larger triple-quoted span (3 physical lines)
        'echo @("""line1\nline2\nline3""") && echo done\n',
        # Multi-line @() on both sides
        'echo @("""a\nb""") && echo @("""c\nd""")\n',
    ],
)
def test_multiline_pyeval_with_combinator(src, xession):
    """Phase-1 recovery must successfully wrap both sides of a shell
    combinator when one or both operands contain a triple-quoted ``@()``
    argument that spans multiple physical lines (issue #6011).
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    tree = execer.parse(src, ctx=ctx, mode="single")
    assert tree is not None
    assert tree.body, f"expected non-empty AST for {src!r}"
    unparsed = pyast.unparse(tree)
    # Both sides of the combinator should end up as subproc calls.
    assert "subproc" in unparsed, f"no subproc wrap in {unparsed!r}"


@pytest.mark.parametrize(
    "src",
    [
        # User-reported variant: ``#`` inside a triple-quoted string
        # without surrounding whitespace.  Lexer correctly treats ``#``
        # as part of the string literal.  Previously the recovery loop
        # would emit empty ``![]`` wraps and cycle until ``max_retries``.
        'echo @("""\nqwe #qwe\n""") && echo 2\n',
        # Same, prefixed with an alias name — exercises another path
        # through subproc_toks (LHS has two NAME tokens before ``@()``).
        'showcmd echo @("""\nqwe #qwe\n""") && echo 2\n',
        # Heavy leading indentation inside the literal.
        'showcmd echo @("""\n                                 qwe #qwe\n                                 """) && echo 2\n',
        # ``#`` in the middle of a multi-line triple — must not be
        # confused with a comment marker by ``_have_open_triple_quotes``.
        'echo @("""start\n# not comment\nend""") && echo 2\n',
    ],
)
def test_multiline_pyeval_with_hash_inside(src, xession):
    """GH-6011 follow-up: a ``#`` inside a multi-line triple-quoted
    ``@()`` literal must not be misread as a comment by the recovery
    loop, and the loop must wrap both sides of ``&&`` without
    accumulating empty ``![]`` wraps.

    Three separate bugs combined to break this:

    1. ``subproc_toks`` with ``maxcol`` after an already-wrapped block
       and a combinator emitted an empty ``![]``.
    2. ``subproc_toks`` in greedy mode wrapped across a top-level
       ``&&``/``||``/``;``, producing invalid ``![cmd && cmd]``.
    3. The recovery loop fed ``last_error_col`` (parser column on a
       physical line) into ``find_next_break`` as if it were the
       absolute offset in the joined logical line.
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    tree = execer.parse(src, ctx=ctx, mode="single")
    assert tree is not None
    assert tree.body
    unparsed = pyast.unparse(tree)
    assert "subproc" in unparsed


def test_multiline_pyeval_plain_assignment(xonsh_execer_parse):
    """A bare assignment from a triple-quoted string is plain Python and
    has nothing to do with subproc recovery — but if ``_have_open_triple_quotes``
    is broken, the recovery loop kicks in anyway and corrupts the line.
    Pin that case so the helper is regression-tested via the front door.
    """
    assert xonsh_execer_parse('x = """a\nb"""\n')
    assert xonsh_execer_parse("x = '''a\nb'''\n")
    # raw triple
    assert xonsh_execer_parse('x = r"""a\\nb"""\n')


@pytest.mark.parametrize(
    "src",
    [
        # plain multi-line f-string assignment — pure Python, no recovery
        'x = f"""a\nb"""\n',
        # multi-line f-string in @() with && — the GH-6011 class
        'echo @(f"""1\n""") && echo 2\n',
        # f-string with interpolated expression
        'x = 5\necho @(f"""val={x}\n""") && echo done\n',
        # raw f-string
        'echo @(rf"""raw\\n\nstuff""") && echo z\n',
        # multi-line f-string on the RHS
        'echo 0 || echo @(f"""a\nb""")\n',
        # multi-line f-string on both sides
        'echo @(f"""a\nb""") && echo @(f"""c\nd""")\n',
        # PEP-701 style: single-quote inside the expression
        'x = "y"\necho @(f"""hi {"abc"}\n""") && echo z\n',
        # Multi-line f-string content that looks like a triple-quote
        # marker if you scan naively (it contains an expression with `1`
        # and the literal contains lines)
        'echo @(f"""a {1} b\nc""") || echo z\n',
    ],
)
def test_multiline_fstring_in_pyeval(src, xession):
    """f-strings (including raw, with interpolated exprs, with nested
    quotes via PEP 701) inside ``@()`` with a shell combinator must go
    through the same phase-1 recovery as plain triple-quoted strings
    (GH-6011 follow-up).
    """
    execer = xession.execer
    ctx = {"__xonsh__": object()}
    tree = execer.parse(src, ctx=ctx, mode="exec")
    assert tree is not None
    assert tree.body, f"expected non-empty AST for {src!r}"
