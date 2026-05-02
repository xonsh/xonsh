"""End-to-end tests for ``CtxAwareTransformer.try_subproc_toks`` in eval mode.

Regression coverage for GH-6386: with the ``coconut`` xontrib loaded,
``CtxAwareTransformer.mode`` is forced to ``"eval"`` so the whole
stripped logical line is fed to ``subproc_toks``.  When phase 1 has
already wrapped part of the line as ``![…]`` (e.g. for
``echo && echo hi`` → ``echo && ![echo hi]``), the eval-mode wrap of
the remaining bare ``Name`` used to produce ``![![echo hi]]`` (invalid
xonsh), the parser raised ``SyntaxError``, ``try_subproc_toks``
swallowed it, and the bare ``Name('echo')`` survived to runtime as a
``NameError``.  A second variant silently miscompiled
``cmd1 && cmd2`` (both bare, both single-token) into ``cmd2 && cmd2``.

The tests reproduce both classes without depending on coconut by
driving ``CtxAwareTransformer`` in eval mode directly via the same
``mode = "eval"`` flip the coconut xontrib performs (see
``coconut.integrations.CoconutXontribLoader.new_try_subproc_toks``).
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
