"""Tests for pipeline teardown under Ctrl+C (SIGINT).

Regression tests for:
- ValueError "I/O operation on closed file" when Ctrl+C interrupts a
  pipeline of alias commands like `!(a | a | a)`.
- ProcProxy.wait() called twice causing duplicated output.
- Deadlock when an ExecAlias whose source already contains a pipe is
  itself used inside an outer pipeline.
"""

import io
from types import SimpleNamespace

import pytest

from xonsh.procs.proxies import ProcProxy, parse_proxy_return
from xonsh.pytest.tools import skip_if_on_windows


def test_parse_proxy_return_writes_str_once():
    """parse_proxy_return('ok', stdout, stderr) writes 'ok' exactly once."""
    buf = io.StringIO()
    parse_proxy_return("ok", buf, io.StringIO())
    assert buf.getvalue() == "ok"


def test_proc_proxy_wait_not_idempotent(xonsh_session):
    """ProcProxy.wait() re-runs parse_proxy_return — double call duplicates output."""
    stdout = io.StringIO()
    proc = ProcProxy(
        lambda: "ok",
        [],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    proc.spec = SimpleNamespace(stack=None, last_in_pipeline=True)

    proc.wait()
    first = stdout.getvalue()
    proc.wait()
    second = stdout.getvalue()

    assert first == "ok"
    assert second == "okok", (
        "wait() is not idempotent — this is why _close_proc must not call it"
    )


def test_close_proc_skips_non_thread_procs():
    """_close_proc must only join() threads, not call wait() on ProcProxy."""
    proc = ProcProxy.__new__(ProcProxy)
    # ProcProxy has no join — _close_proc's `hasattr(p, 'join')` guard must skip it
    assert not hasattr(proc, "join")


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_exec_alias_with_inner_pipe_in_outer_pipe(xonsh_session):
    """ExecAlias whose source already contains a pipe, used inside an outer
    pipeline, must not deadlock.

    Reproducer::

        aliases['aaa'] = 'seq 1 100000 | grep 5'
        aaa | head -3

    The inner pipeline runs inside the ExecAlias's ProcProxyThread.  When
    the outer downstream (head) exits early, the inner pipeline must still
    be able to terminate.  The deadlock surfaced because ``iterraw`` only
    closed pipe-writer fds of finished upstream procs while
    ``check_prev_done`` was False — and any byte of downstream output
    flipped it True, leaving the parent's copy of the inner pipe writer
    open and preventing the inner downstream from ever observing EOF.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False
    # ``--color=never``: on FreeBSD (and Linux distros that ship grep as an
    # alias to ``grep --color=auto``) the BSD grep auto-detects an
    # interactive context inside the test PTY and wraps matches in ANSI
    # escapes, breaking the equality assertion below.
    xonsh_session.aliases["aaa"] = "seq 1 100000 | grep --color=never 5"

    # Early-close downstream
    out = xonsh_session.execer.eval("$(aaa | head -3)")
    assert out.strip().splitlines() == ["5", "15", "25"]

    # Full-drain downstream — would also hang under the bug because the
    # inner pipeline never reaches its own _close_prev_procs() while the
    # parent still holds the seq→grep write fd.
    out = xonsh_session.execer.eval("$(aaa | wc -l)")
    assert out.strip() == "40951"  # count of numbers 1..100000 containing '5'
