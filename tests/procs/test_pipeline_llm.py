"""Tests for pipeline teardown under Ctrl+C (SIGINT).

Regression tests for:
- ValueError "I/O operation on closed file" when Ctrl+C interrupts a
  pipeline of alias commands like `!(a | a | a)`.
- ProcProxy.wait() called twice causing duplicated output.
"""

import io
import os
import signal
from types import SimpleNamespace
from unittest.mock import patch

from xonsh.procs.proxies import ProcProxy, ProcProxyThread, parse_proxy_return


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
