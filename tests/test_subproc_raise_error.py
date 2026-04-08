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
