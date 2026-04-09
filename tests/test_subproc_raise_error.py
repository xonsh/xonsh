"""Tests for ``$XONSH_SUBPROC_RAISE_ERROR`` and the AST wrapping that
implements its semantics (see ``xonsh.parsers.base.wrap_subproc_raise_checks``
and ``xonsh.built_ins.subproc_check_boolop``).

The spec these tests pin down:

* ``$XONSH_SUBPROC_RAISE_ERROR`` (default ``True``) raises a
  ``CalledProcessError`` when the *final* command of a statement
  (standalone or the result of an ``&&``/``||`` chain) returns a
  non-zero exit status.
* ``$XONSH_SUBPROC_CMD_RAISE_ERROR`` (default ``False``) is independent
  and raises on *any* failing pipeline.
* Captured forms (``$()``, ``!()``, ``@$()``) are exempt from the
  chain-result check — the user takes full responsibility.
* ``@error_ignore`` suppresses the raise even when the chain ends in
  failure.
* ``@error_raise`` always raises immediately, even mid-chain.
"""

import ast
from subprocess import CalledProcessError

import pytest

from xonsh.parsers.base import wrap_subproc_raise_checks
from xonsh.pytest.tools import skip_if_on_windows

# ---------------------------------------------------------------------------
# AST-level wrapping
# ---------------------------------------------------------------------------


def _unparse(tree):
    """Helper that produces a stable, short string of the wrapped tree."""
    return ast.unparse(tree).replace("__xonsh__.", "_xs.")


def test_wrap_standalone_bare_command(xonsh_execer):
    """Bare ``ls nono`` becomes
    ``subproc_check_boolop(subproc_captured_hiddenobject(...))``.
    """
    tree = xonsh_execer.parse("ls nono\n", ctx=None)
    src = _unparse(tree)
    assert "_xs.subproc_check_boolop(_xs.subproc_captured_hiddenobject" in src


def test_wrap_boolop_chain(xonsh_execer):
    """``echo 1 && echo 2`` wraps the BoolOp and tags both operands
    with ``in_boolop=True``.
    """
    tree = xonsh_execer.parse("echo 1 && echo 2\n", ctx=None)
    src = _unparse(tree)
    assert "_xs.subproc_check_boolop(" in src
    assert src.count("in_boolop=True") == 2
    assert " and " in src


def test_wrap_does_not_double_wrap_boolop_in_stmt(xonsh_execer):
    """A BoolOp at statement-value position is wrapped exactly once."""
    tree = xonsh_execer.parse("echo 1 || echo 2\n", ctx=None)
    src = _unparse(tree)
    assert src.count("subproc_check_boolop") == 1


def test_wrap_skips_captured_object_form(xonsh_execer):
    """``cp = !(ls nono)`` MUST NOT be wrapped — captured forms are the
    user's responsibility.
    """
    tree = xonsh_execer.parse("cp = !(ls nono)\n", ctx=None)
    src = _unparse(tree)
    assert "subproc_check_boolop" not in src
    assert "subproc_captured_object" in src


def test_wrap_includes_captured_stdout_form(xonsh_execer):
    """``cp = $(ls nono)`` IS wrapped — per spec only ``!(...)`` is the
    "user takes full responsibility" exemption; ``$()`` raises on a
    non-zero rc just like every other subproc form.
    """
    tree = xonsh_execer.parse("cp = $(ls nono)\n", ctx=None)
    src = _unparse(tree)
    assert "subproc_check_boolop" in src
    assert "subproc_captured_stdout" in src


def test_wrap_includes_uncaptured_bracket_form(xonsh_execer):
    """``cp = ![ls nono]`` IS wrapped — ``![...]`` is the side-effect
    form, not a capture.
    """
    tree = xonsh_execer.parse("cp = ![ls nono]\n", ctx=None)
    src = _unparse(tree)
    assert "subproc_check_boolop" in src


def test_wrap_skips_pure_python_boolop(xonsh_execer):
    """Pure-Python ``a and b`` (no subproc helpers) is left untouched."""
    tree = xonsh_execer.parse("x = 1 and 2\n", ctx=None)
    src = _unparse(tree)
    assert "subproc_check_boolop" not in src


def test_wrap_semicolon_separated_statements(xonsh_execer):
    """``echo 1 || echo 2; ls nono`` wraps both statements: the BoolOp
    on the first, and the standalone command on the second.
    """
    tree = xonsh_execer.parse("echo 1 || echo 2; ls nono\n", ctx=None)
    src = _unparse(tree)
    # Two distinct wrappers — one per statement.
    assert src.count("subproc_check_boolop") == 2


def test_wrap_subproc_raise_checks_is_idempotent(xonsh_execer):
    """Re-running the wrapper on an already-wrapped tree must not add
    a second layer.
    """
    tree = xonsh_execer.parse("ls nono\n", ctx=None)
    once = _unparse(tree)
    twice = _unparse(wrap_subproc_raise_checks(tree))
    assert once == twice
    assert once.count("subproc_check_boolop") == 1


# ---------------------------------------------------------------------------
# Runtime behavior — drives the wrapper end-to-end via the execer.
# ---------------------------------------------------------------------------


@pytest.fixture
def raise_env(xonsh_session, monkeypatch):
    """Default-ish env for the new semantics."""
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_RAISE_ERROR", True)
    return xonsh_session.env


@skip_if_on_windows
def test_standalone_failure_raises(xonsh_execer, raise_env):
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope_path_no_exist__\n")


@skip_if_on_windows
def test_standalone_success_does_not_raise(xonsh_execer, raise_env):
    xonsh_execer.exec("echo ok\n")


@skip_if_on_windows
def test_and_chain_both_succeed(xonsh_execer, raise_env):
    xonsh_execer.exec("echo a && echo b\n")


@skip_if_on_windows
def test_and_chain_first_fails_raises(xonsh_execer, raise_env):
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__ && echo never\n")


@skip_if_on_windows
def test_and_chain_second_fails_raises(xonsh_execer, raise_env):
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo ok && ls /__nope__\n")


@skip_if_on_windows
def test_or_chain_first_succeeds(xonsh_execer, raise_env):
    """``echo ok || ls /__nope__`` — first succeeds, second never runs."""
    xonsh_execer.exec("echo ok || ls /__nope__\n")


@skip_if_on_windows
def test_or_chain_first_fails_second_succeeds(xonsh_execer, raise_env):
    xonsh_execer.exec("ls /__nope__ || echo fb\n")


@skip_if_on_windows
def test_or_chain_both_fail_raises(xonsh_execer, raise_env):
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope1__ || ls /__nope2__\n")


@skip_if_on_windows
def test_semicolon_second_stmt_fails_raises(xonsh_execer, raise_env):
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo a || echo b; ls /__nope__\n")


@skip_if_on_windows
def test_semicolon_both_succeed(xonsh_execer, raise_env):
    xonsh_execer.exec("echo a; echo b\n")


@skip_if_on_windows
def test_captured_object_form_does_not_raise(xonsh_execer, raise_env):
    """``!()`` is full capture; user takes responsibility."""
    xonsh_execer.exec("p = !(ls /__nope__)\n")


@skip_if_on_windows
def test_captured_stdout_form_raises(xonsh_execer, raise_env):
    """Per spec only ``!(...)`` is the responsibility-opt-out form;
    ``$(...)`` still raises on a failing command.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("p = $(ls /__nope__ 2>/dev/null)\n")


@skip_if_on_windows
def test_uncaptured_bracket_form_raises(xonsh_execer, raise_env):
    """``$[ls nono]`` raises even though the helper returns ``None``;
    the wrapper falls back to ``XSH.lastcmd`` to read the rc.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("$[ls /__nope__]\n")


@skip_if_on_windows
def test_inject_form_raises(xonsh_execer, raise_env):
    """``@$(ls nono)`` standalone raises — the inject helper
    self-checks its just-completed pipeline.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@$(ls /__nope__)\n")


@skip_if_on_windows
def test_inject_inside_outer_command_raises(xonsh_execer, raise_env):
    """``echo @$(ls nono)`` raises on the *inner* failure even though
    the outer ``echo`` would have succeeded with no extra args.  Without
    helper-level self-raise the wrapper would only see the outer pipeline.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo @$(ls /__nope__)\n")


@skip_if_on_windows
def test_disabling_raise_error_var(xonsh_execer, raise_env, monkeypatch):
    """``XONSH_SUBPROC_RAISE_ERROR=False`` reverts to non-raising."""
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_RAISE_ERROR", False)
    xonsh_execer.exec("ls /__nope__\n")
    xonsh_execer.exec("ls /__nope__ && echo never\n")


@skip_if_on_windows
def test_cmd_raise_error_overrides_chain_skip(xonsh_execer, raise_env, monkeypatch):
    """``XONSH_SUBPROC_CMD_RAISE_ERROR=True`` raises on the *first*
    failing pipeline in a chain — even before the BoolOp short-circuit
    has a chance to fall through.
    """
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", True)
    with pytest.raises(CalledProcessError):
        # The `||` would normally rescue this, but per-command raising
        # short-circuits before the fallback runs.
        xonsh_execer.exec("ls /__nope__ || echo fb\n")


@skip_if_on_windows
def test_error_ignore_in_chain(xonsh_execer, raise_env):
    """``echo 1 && @error_ignore ls /__nope__`` — final pipeline is the
    failing ``ls``, but ``@error_ignore`` suppresses the raise.
    """
    xonsh_execer.exec("echo 1 && @error_ignore ls /__nope__\n")


@skip_if_on_windows
def test_error_ignore_standalone(xonsh_execer, raise_env):
    xonsh_execer.exec("@error_ignore ls /__nope__\n")


@skip_if_on_windows
def test_error_raise_standalone(xonsh_execer, raise_env, monkeypatch):
    """``@error_raise`` raises even when CMD_RAISE_ERROR is False."""
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_raise ls /__nope__\n")


@skip_if_on_windows
def test_error_raise_in_chain_raises_immediately(xonsh_execer, raise_env):
    """``@error_raise`` raises mid-chain even when ``||`` would otherwise
    rescue, because the user explicitly opted in to raise on this cmd.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_raise ls /__nope__ || echo fb\n")


# ---------------------------------------------------------------------------
# Edge cases — pipes, longer chains, decorator interactions, exception
# attributes, statement-after-raise.
# ---------------------------------------------------------------------------


@skip_if_on_windows
def test_pipe_failure_raises(xonsh_execer, raise_env):
    """A pipeline whose final stage fails raises just like a single
    command — ``echo hi | grep x`` ends with rc=1 from grep.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo hi | grep x\n")


@skip_if_on_windows
def test_three_cmd_and_chain_last_fails(xonsh_execer, raise_env):
    """``cmd1 && cmd2 && cmd3`` where the last fails — raises on the
    last pipeline (the one that determined the chain result).
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo a && echo b && ls /__nope__\n")


@skip_if_on_windows
def test_three_cmd_and_chain_first_fails(xonsh_execer, raise_env):
    """``cmd1 && cmd2 && cmd3`` where the first fails — short-circuits
    on the first failing pipeline; later commands never run.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__ && echo never1 && echo never2\n")


@skip_if_on_windows
def test_mixed_and_or_chain_rescued(xonsh_execer, raise_env):
    """``ls nono && echo n || echo fb`` — Python precedence is
    ``(ls and echo_n) or echo_fb``.  ``ls`` falsy → inner ``and`` returns
    ``ls``; outer ``or`` evaluates ``echo fb`` (success).  No raise.
    """
    xonsh_execer.exec("ls /__nope__ && echo n || echo fb\n")


@skip_if_on_windows
def test_mixed_and_or_chain_middle_fail_rescued(xonsh_execer, raise_env):
    """``echo a && ls nono || echo fb`` — ``ls`` (the second op of the
    inner ``and``) fails; the outer ``or`` falls back to ``echo fb``.
    """
    xonsh_execer.exec("echo a && ls /__nope__ || echo fb\n")


@skip_if_on_windows
def test_error_ignore_overrides_cmd_raise_error(xonsh_execer, raise_env, monkeypatch):
    """``@error_ignore`` wins over ``$XONSH_SUBPROC_CMD_RAISE_ERROR=True``."""
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", True)
    xonsh_execer.exec("@error_ignore ls /__nope__\n")


@skip_if_on_windows
def test_error_raise_overrides_disabled_raise_error(
    xonsh_execer, raise_env, monkeypatch
):
    """``@error_raise`` raises even when *both* ``$XONSH_SUBPROC_RAISE_ERROR``
    and ``$XONSH_SUBPROC_CMD_RAISE_ERROR`` are False — the decorator is the
    explicit per-command opt-in.
    """
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_RAISE_ERROR", False)
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_raise ls /__nope__\n")


@skip_if_on_windows
def test_called_process_error_attributes(xonsh_execer, raise_env):
    """The raised ``CalledProcessError`` carries the right ``returncode``
    and ``cmd`` so user code can ``except`` and inspect it.
    """
    with pytest.raises(CalledProcessError) as exc_info:
        xonsh_execer.exec("ls /__nope_specific__\n")
    err = exc_info.value
    assert err.returncode != 0
    # ``cmd`` is the original argv list xonsh passed to the subprocess.
    assert "ls" in err.cmd
    assert "/__nope_specific__" in err.cmd


@skip_if_on_windows
def test_statement_after_raise_does_not_run(xonsh_execer, raise_env, capsys):
    """A failing statement aborts execution of the script — subsequent
    statements never run.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__\necho should_not_appear\n")
    out = capsys.readouterr().out
    assert "should_not_appear" not in out


# ---------------------------------------------------------------------------
# Exhaustive chain combinations — every 2/3-element chain with &&, ||,
# pipes, decorators, and both env vars.
# ---------------------------------------------------------------------------


@skip_if_on_windows
def test_three_cmd_or_chain_all_fail(xonsh_execer, raise_env):
    """``fail || fail || fail`` — all fail, chain result is falsy → raise."""
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__n1__ || ls /__n2__ || ls /__n3__\n")


@skip_if_on_windows
def test_three_cmd_or_chain_last_succeeds(xonsh_execer, raise_env):
    """``fail || fail || echo ok`` — last succeeds, chain result is truthy."""
    xonsh_execer.exec("ls /__n1__ || ls /__n2__ || echo ok\n")


@skip_if_on_windows
def test_three_cmd_or_chain_middle_succeeds(xonsh_execer, raise_env):
    """``fail || echo ok || fail`` — middle succeeds, ``or`` short-circuits."""
    xonsh_execer.exec("ls /__n1__ || echo ok || ls /__n3__\n")


@skip_if_on_windows
def test_three_cmd_or_chain_first_succeeds(xonsh_execer, raise_env):
    """``echo ok || fail || fail`` — first succeeds, rest never evaluated."""
    xonsh_execer.exec("echo ok || ls /__n2__ || ls /__n3__\n")


@skip_if_on_windows
def test_or_then_and_chain_rescued(xonsh_execer, raise_env):
    """``fail || echo ok && echo yes`` — Python precedence:
    ``fail or (echo_ok and echo_yes)``.  ``fail`` is falsy → evaluate
    ``echo ok and echo yes`` → both truthy → no raise.
    """
    xonsh_execer.exec("ls /__nope__ || echo ok && echo yes\n")


@skip_if_on_windows
def test_or_then_and_chain_second_part_fails(xonsh_execer, raise_env):
    """``fail || echo ok && fail`` — ``fail or (ok and fail)`` →
    inner ``and`` returns ``fail`` → that's the chain result → raise.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__ || echo ok && ls /__n2__\n")


@skip_if_on_windows
def test_and_then_or_all_fail(xonsh_execer, raise_env):
    """``fail && echo n || fail`` — ``(fail and echo_n) or fail2``.
    Inner ``and`` short-circuits to ``fail`` (falsy), outer ``or``
    evaluates ``fail2`` (also falsy) → raise.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__n1__ && echo n || ls /__n2__\n")


@skip_if_on_windows
def test_pipe_in_and_chain_pipe_fails(xonsh_execer, raise_env):
    """``echo ok | grep x && echo n`` — pipe exits non-zero (grep no match),
    ``and`` short-circuits → chain result is the failing pipe → raise.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo ok | grep x && echo n\n")


@skip_if_on_windows
def test_pipe_in_or_chain_pipe_fails_rescued(xonsh_execer, raise_env):
    """``echo ok | grep x || echo fb`` — pipe fails, ``or`` evaluates
    ``echo fb`` (success) → no raise.
    """
    xonsh_execer.exec("echo ok | grep x || echo fb\n")


@skip_if_on_windows
def test_pipe_in_and_chain_pipe_succeeds(xonsh_execer, raise_env):
    """``echo ok | grep ok && echo yes`` — pipe succeeds, ``and`` continues,
    ``echo yes`` succeeds → no raise.
    """
    xonsh_execer.exec("echo ok | grep ok && echo yes\n")


@skip_if_on_windows
def test_error_ignore_mid_and_chain(xonsh_execer, raise_env):
    """``echo 1 && @error_ignore ls /__nope__ && echo 2`` —
    ``@error_ignore`` suppresses the mid-chain failure, but Python
    ``and`` still sees the falsy HiddenCommandPipeline and short-circuits,
    so ``echo 2`` never runs.  The chain result is the failing pipeline
    with ``@error_ignore`` → no raise.
    """
    xonsh_execer.exec(
        "echo 1 && @error_ignore ls /__nope__\n"
    )


@skip_if_on_windows
def test_error_raise_first_in_or_chain(xonsh_execer, raise_env):
    """``@error_raise fail || echo fb`` — ``@error_raise`` raises immediately
    at the pipeline level, before ``||`` gets a chance to rescue.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_raise ls /__nope__ || echo fb\n")


@skip_if_on_windows
def test_error_raise_second_in_and_chain(xonsh_execer, raise_env):
    """``echo ok && @error_raise fail`` — first succeeds, ``and`` continues,
    ``@error_raise`` on the second raises immediately.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo ok && @error_raise ls /__nope__\n")


@skip_if_on_windows
def test_error_raise_on_success_does_not_raise(xonsh_execer, raise_env):
    """``@error_raise echo ok`` — command succeeds, no raise despite decorator."""
    xonsh_execer.exec("@error_raise echo ok\n")


@skip_if_on_windows
def test_both_env_vars_true_standalone_fail(xonsh_execer, raise_env, monkeypatch):
    """Both ``$XONSH_SUBPROC_RAISE_ERROR`` and ``$XONSH_SUBPROC_CMD_RAISE_ERROR``
    are True — standalone failure raises (via CMD level).
    """
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", True)
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__\n")


@skip_if_on_windows
def test_both_env_vars_true_chain_first_fail(xonsh_execer, raise_env, monkeypatch):
    """Both env vars True — ``fail || echo fb``: CMD_RAISE_ERROR fires on the
    first pipeline before ``||`` can rescue.
    """
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", True)
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__ || echo fb\n")


@skip_if_on_windows
def test_both_env_vars_false_no_raise(xonsh_execer, raise_env, monkeypatch):
    """Both env vars False — nothing raises."""
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_RAISE_ERROR", False)
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    xonsh_execer.exec("ls /__nope__\n")
    xonsh_execer.exec("ls /__n1__ && echo n\n")
    xonsh_execer.exec("ls /__n1__ || ls /__n2__\n")


@skip_if_on_windows
def test_error_ignore_overrides_both_env_vars(xonsh_execer, raise_env, monkeypatch):
    """``@error_ignore`` suppresses even when both env vars are True."""
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", True)
    xonsh_execer.exec("@error_ignore ls /__nope__\n")


@skip_if_on_windows
def test_captured_object_in_chain_does_not_raise(xonsh_execer, raise_env):
    """``p = !(fail) && echo yes`` — ``!(...)`` is exempt, so ``p`` is
    assigned the falsy pipeline. ``and`` short-circuits; no raise because
    the final value is the ``!(...)`` exempt pipeline.
    """
    xonsh_execer.exec("p = !(ls /__nope__)\n")


@skip_if_on_windows
def test_semicolon_first_fails_second_succeeds(xonsh_execer, raise_env):
    """``fail; echo ok`` — first statement raises before the second runs."""
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("ls /__nope__; echo ok\n")


@skip_if_on_windows
def test_semicolon_first_succeeds_second_fails(xonsh_execer, raise_env):
    """``echo ok; fail`` — first statement succeeds, second raises."""
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo ok; ls /__nope__\n")


@skip_if_on_windows
def test_four_cmd_and_chain_all_succeed(xonsh_execer, raise_env):
    """``a && b && c && d`` — all succeed → no raise."""
    xonsh_execer.exec("echo a && echo b && echo c && echo d\n")


@skip_if_on_windows
def test_four_cmd_or_chain_all_fail(xonsh_execer, raise_env):
    """``f || f || f || f`` — all fail → raise."""
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec(
            "ls /__n1__ || ls /__n2__ || ls /__n3__ || ls /__n4__\n"
        )


@skip_if_on_windows
def test_four_cmd_or_chain_last_succeeds(xonsh_execer, raise_env):
    """``f || f || f || echo ok`` — last succeeds → no raise."""
    xonsh_execer.exec("ls /__n1__ || ls /__n2__ || ls /__n3__ || echo ok\n")


@skip_if_on_windows
def test_pipe_success_standalone(xonsh_execer, raise_env):
    """``echo hello | grep hello`` — pipe succeeds → no raise."""
    xonsh_execer.exec("echo hello | grep hello\n")


@skip_if_on_windows
def test_pipe_failure_standalone(xonsh_execer, raise_env):
    """``echo hello | grep nope`` — pipe fails → raise."""
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("echo hello | grep nope\n")


@skip_if_on_windows
def test_error_raise_with_cmd_raise_error_false(xonsh_execer, raise_env, monkeypatch):
    """``@error_raise`` still raises when ``CMD_RAISE_ERROR=False`` and
    ``RAISE_ERROR=False`` — decorator is the ultimate override.
    """
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_RAISE_ERROR", False)
    monkeypatch.setitem(raise_env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False)
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_raise ls /__nope__\n")


@skip_if_on_windows
def test_error_ignore_in_or_chain_all_fail(xonsh_execer, raise_env):
    """``@error_ignore fail || fail`` — first has ignore, but ``or`` sees
    falsy and evaluates the second (no decorator) which also fails.
    Chain result is the second pipeline (no ignore) → raise.
    """
    with pytest.raises(CalledProcessError):
        xonsh_execer.exec("@error_ignore ls /__n1__ || ls /__n2__\n")


@skip_if_on_windows
def test_error_ignore_last_in_or_chain(xonsh_execer, raise_env):
    """``fail || @error_ignore fail`` — first fails, ``or`` evaluates
    second (also fails but has ``@error_ignore``).  Chain result is
    the ``@error_ignore`` pipeline → no raise.
    """
    xonsh_execer.exec("ls /__n1__ || @error_ignore ls /__n2__\n")


# ---------------------------------------------------------------------------
# Interactive prompt display — ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR``
#
# These tests drive ``BaseShell.default()`` directly, which is the
# interactive line handler.  Scripts (``-c`` / ``./foo.xsh`` / stdin
# script mode) never reach ``default()``, so their error display is
# unaffected by ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR``.
# ---------------------------------------------------------------------------


@pytest.fixture
def base_shell(xonsh_execer, xonsh_session):
    """A raw ``BaseShell`` attached to the current session's execer
    and context.  Just enough to drive ``default()`` against a real
    subprocess command.
    """
    from xonsh.shells.base_shell import BaseShell

    shell = BaseShell(xonsh_execer, xonsh_session.ctx, completer=False)
    return shell


@skip_if_on_windows
def test_prompt_suppresses_calledprocesserror_by_default(base_shell, raise_env, capsys):
    """With the default ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR=False`` the
    interactive prompt does NOT print ``CalledProcessError: ...`` — the
    command's own stderr is still shown (by the subprocess itself), but
    xonsh stays quiet.
    """
    base_shell.default("ls /__nope_specific__\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" not in err


@skip_if_on_windows
def test_prompt_shows_calledprocesserror_when_opted_in(
    base_shell, raise_env, capsys, monkeypatch
):
    """``$XONSH_PROMPT_SHOW_SUBPROC_ERROR=True`` restores the historical
    behavior of printing the ``CalledProcessError`` after a failing
    command at the prompt.
    """
    monkeypatch.setitem(raise_env, "XONSH_PROMPT_SHOW_SUBPROC_ERROR", True)
    base_shell.default("ls /__nope_specific__\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" in err


@skip_if_on_windows
def test_prompt_always_shows_error_raise_decorator(base_shell, raise_env, capsys):
    """``@error_raise`` is an explicit per-command opt-in that *always*
    shows the exception, regardless of
    ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR``.
    """
    base_shell.default("@error_raise ls /__nope_specific__\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" in err


@skip_if_on_windows
def test_prompt_chain_last_failing_also_suppressed(base_shell, raise_env, capsys):
    """``echo ok && ls /__nope__`` — chain ends on a failing pipeline.
    Same suppression rule applies at the prompt.
    """
    base_shell.default("echo ok && ls /__nope_specific__\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" not in err


@skip_if_on_windows
def test_prompt_chain_rescued_no_suppress_needed(base_shell, raise_env, capsys):
    """``ls /__nope__ || echo fb`` — chain rescued by ``||``, no
    exception is raised to begin with, so nothing to suppress.
    """
    base_shell.default("ls /__nope_specific__ || echo fb\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" not in err


@skip_if_on_windows
def test_prompt_success_does_not_touch_display(base_shell, raise_env, capsys):
    """Sanity: a successful command at the prompt stays silent and
    doesn't touch the error display path.
    """
    base_shell.default("echo ok\n")
    err = capsys.readouterr().err
    assert "CalledProcessError" not in err


@skip_if_on_windows
def test_prompt_last_return_code_set_even_when_suppressed(
    base_shell, raise_env, xonsh_session
):
    """Even when the exception display is suppressed, the failing
    pipeline's return code is still recorded so ``$LAST_RETURN_CODE``
    works as expected.  ``_apply_to_history`` on the pipeline sets
    ``hist.last_cmd_rtn`` to the real returncode before
    ``_append_history`` propagates it into ``$LAST_RETURN_CODE``.
    """
    base_shell.default("ls /__nope_specific__\n")
    assert xonsh_session.env["LAST_RETURN_CODE"] != 0
