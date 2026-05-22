"""LLM-generated tests for ``xonsh.procs.pipelines``."""

from xonsh.procs.pipelines import CommandPipeline
from xonsh.pytest.tools import skip_if_on_windows


@skip_if_on_windows
def test_returncode_finalizes_unreaped_proc(xonsh_session):
    """Regression for #6456: if ``tee_stdout`` bails before reaping
    (intermittent under load), ``end()`` leaves ``proc.returncode``
    unset.  ``CommandPipeline.returncode`` must still produce a
    definite int — not ``None`` — so the raise-check helpers don't
    conflate "undetermined" with "succeeded".

    Use a successful ``!(true)`` as the carrier pipeline (so the test
    is independent of ``$XONSH_SUBPROC_CMD_RAISE_ERROR``, which the
    in-CI ``run-tests.xsh`` enables) and inject the bug state by
    swapping ``pipeline.proc`` for one whose ``returncode`` is ``None``
    until ``poll()`` is called.
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()
    assert pipeline.proc.returncode == 0  # sanity

    real_rc = 7

    class _UnreapedProc:
        returncode = None

        def poll(self):
            self.returncode = real_rc
            return real_rc

    pipeline.proc = _UnreapedProc()
    assert pipeline.returncode == real_rc


@skip_if_on_windows
def test_returncode_stays_none_when_proc_still_alive(xonsh_session):
    """The poll-based fallback added for #6456 must not block: a
    still-alive proc keeps ``returncode`` at ``None`` so suspended /
    background pipelines still report "undetermined" to the
    raise-checks (which intentionally skip on ``None``).
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()
    assert pipeline.proc.returncode == 0

    class _AliveProc:
        returncode = None

        def poll(self):
            return None  # proc still running

    pipeline.proc = _AliveProc()
    assert pipeline.returncode is None


@skip_if_on_windows
def test_returncode_poll_failure_trace(xonsh_session, monkeypatch, capsys):
    """When ``$XONSH_SUBPROC_TRACE`` is enabled, a failing ``poll()`` in
    the #6456 fallback must surface its exception on stderr instead of
    silently swallowing it — so that the rare "proc disappeared" path
    is debuggable.  With trace off, the swallow stays silent.
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()

    class _PollFails:
        returncode = None

        def poll(self):
            raise RuntimeError("simulated poll failure")

    pipeline.proc = _PollFails()

    # Trace off — silent swallow, returncode is None.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_TRACE", 0)
    assert pipeline.returncode is None
    assert "simulated poll failure" not in capsys.readouterr().err

    # Trace on — exception surfaces on stderr; returncode is still None.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_TRACE", 1)
    assert pipeline.returncode is None
    assert "simulated poll failure" in capsys.readouterr().err
