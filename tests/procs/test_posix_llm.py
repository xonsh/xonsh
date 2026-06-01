"""Tests for :mod:`xonsh.procs.posix`.

Currently focused on the SIGBREAK (Windows Ctrl+Break) handling added for
issue #4852. The handler methods are pure logic, so they are exercised on
lightweight ``__new__`` instances rather than by spawning real subprocesses.
"""

import signal

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.procs.posix import PopenThread

skip_if_not_on_windows = pytest.mark.skipif(
    not ON_WINDOWS, reason="SIGBREAK / Ctrl+Break only exist on Windows"
)


class _FakeProc:
    """Minimal stand-in for ``subprocess.Popen`` exposing ``poll()``."""

    def __init__(self, rc):
        self._rc = rc

    def poll(self):
        return self._rc


def _bare_popen_thread(*, returncode=None, interrupted=False):
    """A PopenThread skeleton with only the attributes the SIGBREAK
    handlers touch — no thread, no real process."""
    inst = PopenThread.__new__(PopenThread)
    inst._interrupted = interrupted
    inst.old_break_handler = "SENTINEL"
    inst.proc = _FakeProc(returncode)
    return inst


def test_popen_signal_break_marks_interrupted_while_running():
    """While the child is still running, the break only records the
    interrupt; the handler is left in place for the teardown path."""
    inst = _bare_popen_thread(returncode=None)
    inst._signal_break(21, None)
    assert inst._interrupted is True
    assert inst.old_break_handler == "SENTINEL"


def test_popen_signal_break_is_idempotent():
    """A second delivery while already interrupted is a no-op (guards
    against recursive re-entry)."""
    inst = _bare_popen_thread(returncode=0, interrupted=True)
    inst._signal_break(21, None)
    assert inst.old_break_handler == "SENTINEL"


@skip_if_not_on_windows
def test_popen_signal_break_restores_and_chains(monkeypatch):
    """Once the child has exited, the break restores the previous handler
    and chains to it — so the saved ``default_int_handler`` raises the
    catchable KeyboardInterrupt that returns xonsh to its prompt."""
    import xonsh.procs.posix as pmod

    calls = []
    monkeypatch.setattr(pmod.signal, "signal", lambda s, h: calls.append((s, h)))
    inst = _bare_popen_thread(returncode=0)
    inst.old_break_handler = signal.default_int_handler
    inst._disable_cbreak_stdin = lambda: None  # stub TTY restore
    with pytest.raises(KeyboardInterrupt):
        inst._signal_break(int(signal.SIGBREAK), object())
    assert inst._interrupted is True
    assert (signal.SIGBREAK, signal.default_int_handler) in calls
    assert inst.old_break_handler is None


@skip_if_not_on_windows
def test_popen_restore_sigbreak_without_frame_does_not_chain(monkeypatch):
    """Cleanup-path restore (frame=None) reinstalls the old handler but must
    not chain into it (that would raise mid-teardown)."""
    import xonsh.procs.posix as pmod

    calls = []
    monkeypatch.setattr(pmod.signal, "signal", lambda s, h: calls.append((s, h)))
    inst = _bare_popen_thread(returncode=0)
    inst.old_break_handler = signal.default_int_handler
    inst._restore_sigbreak()  # frame=None
    assert (signal.SIGBREAK, signal.default_int_handler) in calls
    assert inst.old_break_handler is None
