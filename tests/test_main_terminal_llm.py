"""Tests for the controlling-terminal startup handshake in xonsh.main.

Covers :func:`xonsh.main._acquire_controlling_terminal`,
:func:`xonsh.main._release_controlling_terminal` and
:func:`xonsh.main._setup_controlling_terminal`. These manipulate process
group and TTY state, so most tests patch out the underlying OS primitives
with a ``FakeOS`` helper instead of exercising them for real — the actual
syscall behaviour is provided by the kernel and is tested at the libc
level, we only care about the policy xonsh wraps around them.
"""

import signal
import sys

import pytest

import xonsh.main
from xonsh.pytest.tools import skip_if_on_windows


@pytest.fixture
def reset_fg_state():
    """Ensure the module-level foreground state is clean around each test.

    The state leaks between tests otherwise because ``_fg_tty_state`` is a
    plain module-level dict, ``_tty_setup_done`` is a module-level flag
    for :func:`_setup_controlling_terminal` idempotency, and
    ``_ttin_ttou_counter`` is a module-level counter for
    :func:`_handle_sig_ttin_ttou` livelock escalation.
    """
    original = dict(xonsh.main._fg_tty_state)
    original_done = xonsh.main._tty_setup_done
    original_counter = xonsh.main._ttin_ttou_counter[0]
    xonsh.main._fg_tty_state["acquired"] = False
    xonsh.main._fg_tty_state["tty_fd"] = -1
    xonsh.main._fg_tty_state["old_fg"] = -1
    xonsh.main._tty_setup_done = False
    xonsh.main._ttin_ttou_counter[0] = 0
    yield
    xonsh.main._fg_tty_state.clear()
    xonsh.main._fg_tty_state.update(original)
    xonsh.main._tty_setup_done = original_done
    xonsh.main._ttin_ttou_counter[0] = original_counter


class FakeOS:
    """A tiny recorder for the OS primitives the handshake touches.

    Tests build a ``FakeOS`` with the desired initial state and then
    monkeypatch the module-level ``os.*`` calls in :mod:`xonsh.main`
    to its methods. Each method either returns the stored value,
    updates state, or raises a configured exception — nothing else.
    """

    def __init__(
        self,
        *,
        pid=1000,
        pgid=999,
        sid=500,
        fg_pgrp=999,
        is_tty=True,
        tcgetpgrp_err=None,
        setpgid_err=None,
        tcsetpgrp_err=None,
        getsid_err=None,
        isatty_err=None,
    ):
        self.pid = pid
        self.pgid = pgid
        self.sid = sid
        self.fg_pgrp = fg_pgrp
        self.is_tty = is_tty
        self.tcgetpgrp_err = tcgetpgrp_err
        self.setpgid_err = setpgid_err
        self.tcsetpgrp_err = tcsetpgrp_err
        self.getsid_err = getsid_err
        self.isatty_err = isatty_err
        # Call log — tests assert on these to verify the expected
        # sequence of syscalls happened (or did not happen).
        self.calls = []

    def getpid(self):
        return self.pid

    def getpgrp(self):
        return self.pgid

    def getsid(self, pid):
        self.calls.append(("getsid", pid))
        if self.getsid_err is not None:
            raise self.getsid_err
        return self.sid

    def isatty(self, fd):
        self.calls.append(("isatty", fd))
        if self.isatty_err is not None:
            raise self.isatty_err
        return self.is_tty

    def tcgetpgrp(self, fd):
        self.calls.append(("tcgetpgrp", fd))
        if self.tcgetpgrp_err is not None:
            raise self.tcgetpgrp_err
        return self.fg_pgrp

    def setpgid(self, pid, pgid):
        self.calls.append(("setpgid", pid, pgid))
        if self.setpgid_err is not None:
            raise self.setpgid_err
        # setpgid(0, 0) means "make me my own leader": pgid := pid.
        if pid == 0 and pgid == 0:
            self.pgid = self.pid

    def tcsetpgrp(self, fd, pgid):
        self.calls.append(("tcsetpgrp", fd, pgid))
        if self.tcsetpgrp_err is not None:
            raise self.tcsetpgrp_err
        self.fg_pgrp = pgid


@pytest.fixture
def fake_tty(monkeypatch):
    """Wire a ``FakeOS`` into ``xonsh.main`` and yield it.

    Also patches ``signal.pthread_sigmask`` to a recording stub so we can
    assert that the handshake masks the right signals. We do NOT touch
    ``sys.stderr`` — pytest already replaces it with a capture fd, and
    since every ``os.*`` call is mocked, the concrete fd value is
    irrelevant. The effective fd is exposed as the second element of
    the yielded tuple so tests can assert against it.
    """
    mask_log = []

    def fake_pthread_sigmask(how, signals):
        mask_log.append((how, set(signals) if signals is not None else None))
        return set()

    monkeypatch.setattr(xonsh.main.signal, "pthread_sigmask", fake_pthread_sigmask)

    try:
        expected_fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        # pytest may wrap stderr with an object whose fileno() errors;
        # skip the tests in that environment rather than run them on a
        # bogus fd.
        pytest.skip("sys.stderr has no usable fileno() under this runner")

    def install(fake):
        monkeypatch.setattr(xonsh.main.os, "getpid", fake.getpid)
        monkeypatch.setattr(xonsh.main.os, "getpgrp", fake.getpgrp)
        monkeypatch.setattr(xonsh.main.os, "getsid", fake.getsid)
        monkeypatch.setattr(xonsh.main.os, "isatty", fake.isatty)
        monkeypatch.setattr(xonsh.main.os, "tcgetpgrp", fake.tcgetpgrp)
        monkeypatch.setattr(xonsh.main.os, "setpgid", fake.setpgid)
        monkeypatch.setattr(xonsh.main.os, "tcsetpgrp", fake.tcsetpgrp)

    yield install, mask_log, expected_fd


@skip_if_on_windows
def test_acquire_returns_false_when_env_disabled(monkeypatch, reset_fg_state):
    """``XONSH_NO_FG_TAKEOVER`` short-circuits the whole handshake."""
    monkeypatch.setenv("XONSH_NO_FG_TAKEOVER", "1")
    assert xonsh.main._acquire_controlling_terminal() is False
    assert xonsh.main._fg_tty_state["acquired"] is False


@skip_if_on_windows
def test_acquire_returns_false_when_not_a_tty(monkeypatch, reset_fg_state, fake_tty):
    """Non-TTY stderr (script mode, piped I/O) is a clean no-op."""
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(is_tty=False)
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is False
    # isatty must be called; we must NOT touch process group state.
    kinds = [c[0] for c in fake.calls]
    assert "isatty" in kinds
    assert "setpgid" not in kinds
    assert "tcsetpgrp" not in kinds


@skip_if_on_windows
def test_acquire_returns_false_when_session_leader(
    monkeypatch, reset_fg_state, fake_tty
):
    """A session leader cannot setpgid itself — skip cleanly."""
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, sid=1000)  # sid == pid ⇒ session leader
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is False
    kinds = [c[0] for c in fake.calls]
    # Must not try to change pgrp or TTY state.
    assert "setpgid" not in kinds
    assert "tcsetpgrp" not in kinds


@skip_if_on_windows
def test_acquire_fast_path_when_already_foreground(
    monkeypatch, reset_fg_state, fake_tty
):
    """If the TTY's fg group is already ours, no work is needed.

    The handshake must not mark state as acquired in this case so the
    ``atexit`` restorer stays a no-op and we never race with the parent
    shell's own ``tcsetpgrp`` on exit.
    """
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=999)
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is True
    # State stays unacquired — nothing to release on shutdown.
    assert xonsh.main._fg_tty_state["acquired"] is False
    kinds = [c[0] for c in fake.calls]
    assert "tcgetpgrp" in kinds
    assert "setpgid" not in kinds
    assert "tcsetpgrp" not in kinds


@skip_if_on_windows
def test_acquire_pid_namespace_unrepresentable_pgid(
    monkeypatch, reset_fg_state, fake_tty
):
    """PID namespace edge case: ``getpgrp`` and ``tcgetpgrp`` both
    return 0 because our real pgid is not representable inside the
    namespace (typical for Flatpak / Bubblewrap / Podman / kubectl
    exec scenarios). The fast path must NOT treat ``0 == 0`` as
    "already foreground" — it must fall through to ``setpgid(0, 0)``
    so we end up with a valid, namespace-visible pgid.

    This reproduces the Flatpak crash where ``tcsetpgrp(fd, 0)``
    later failed with ESRCH and the TTY foreground ended up
    orphaned on a dead subprocess group, ultimately raising
    ``termios.error: (5, 'Input/output error')`` from ptk.
    """
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    # Inside a PID namespace:
    #   - our visible pid is 2 (namespace-local)
    #   - our sid is e.g. 500 (some visible session leader)
    #   - our "real" pgid was inherited from outside the namespace,
    #     so the kernel reports it as 0 (unrepresentable)
    #   - the TTY fg pgrp is also 0 (it belongs to a pgrp outside
    #     the namespace, i.e. the outer bash)
    fake = FakeOS(pid=2, pgid=0, sid=500, fg_pgrp=0)
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is True
    # State IS recorded — we really did acquire foreground via
    # a full setpgid + tcsetpgrp, not via the fast path.
    assert xonsh.main._fg_tty_state["acquired"] is True
    assert xonsh.main._fg_tty_state["old_fg"] == 0
    # setpgid(0, 0) and tcsetpgrp must both have been called.
    kinds = [c[0] for c in fake.calls]
    assert "setpgid" in kinds
    assert "tcsetpgrp" in kinds
    # After setpgid(0, 0) our FakeOS model sets pgid := pid = 2,
    # which is representable inside the namespace.
    assert fake.pgid == 2
    # And tcsetpgrp installed pgid=2 as the TTY foreground.
    assert fake.fg_pgrp == 2


@skip_if_on_windows
def test_acquire_full_handshake_success(monkeypatch, reset_fg_state, fake_tty):
    """Full success path: setpgid then tcsetpgrp, state recorded."""
    install, mask_log, expected_fd = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=42)
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is True
    # State is recorded for the release step.
    assert xonsh.main._fg_tty_state["acquired"] is True
    assert xonsh.main._fg_tty_state["tty_fd"] == expected_fd
    assert xonsh.main._fg_tty_state["old_fg"] == 42
    # The fake kernel now reports us as the fg group.
    assert fake.fg_pgrp == 1000
    assert fake.pgid == 1000
    # The signal mask was blocked and then restored.
    assert len(mask_log) == 2
    assert mask_log[0][0] == signal.SIG_BLOCK
    assert mask_log[1][0] == signal.SIG_SETMASK
    blocked = mask_log[0][1]
    assert signal.SIGTTOU in blocked
    assert signal.SIGTTIN in blocked
    assert signal.SIGTSTP in blocked
    assert signal.SIGCHLD in blocked


@skip_if_on_windows
def test_acquire_returns_false_on_tcgetpgrp_failure(
    monkeypatch, reset_fg_state, fake_tty
):
    """If tcgetpgrp fails, skip without touching setpgid/tcsetpgrp."""
    install, mask_log, expected_fd = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(tcgetpgrp_err=OSError("ENOTTY"))
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is False
    kinds = [c[0] for c in fake.calls]
    assert "setpgid" not in kinds
    assert "tcsetpgrp" not in kinds
    # Mask must still be restored.
    assert len(mask_log) == 2
    assert mask_log[-1][0] == signal.SIG_SETMASK


@skip_if_on_windows
def test_acquire_returns_false_on_setpgid_failure(
    monkeypatch, reset_fg_state, fake_tty
):
    """A PermissionError from setpgid degrades cleanly."""
    install, mask_log, expected_fd = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(fg_pgrp=42, setpgid_err=PermissionError("EPERM"))
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is False
    assert xonsh.main._fg_tty_state["acquired"] is False
    # Mask restored.
    assert mask_log[-1][0] == signal.SIG_SETMASK


@skip_if_on_windows
def test_acquire_returns_false_on_tcsetpgrp_failure(
    monkeypatch, reset_fg_state, fake_tty
):
    """If tcsetpgrp fails we leave setpgid's change in place but do
    not claim success. State is not marked as acquired, so the
    restorer is a no-op.
    """
    install, mask_log, expected_fd = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(fg_pgrp=42, tcsetpgrp_err=OSError("EPERM"))
    install(fake)
    assert xonsh.main._acquire_controlling_terminal() is False
    assert xonsh.main._fg_tty_state["acquired"] is False
    kinds = [c[0] for c in fake.calls]
    assert "setpgid" in kinds  # we did get this far
    assert "tcsetpgrp" in kinds  # and we did try the install
    assert mask_log[-1][0] == signal.SIG_SETMASK


@skip_if_on_windows
def test_release_is_noop_when_not_acquired(monkeypatch, reset_fg_state, fake_tty):
    """Releasing before a successful acquire must not touch the TTY."""
    install, _, _ = fake_tty
    fake = FakeOS()
    install(fake)
    # state is clean from the fixture
    xonsh.main._release_controlling_terminal()
    assert fake.calls == []  # no syscalls at all


@skip_if_on_windows
def test_release_restores_previous_foreground(monkeypatch, reset_fg_state, fake_tty):
    """Full release: tcsetpgrp is called with the old fg pgid."""
    install, mask_log, expected_fd = fake_tty
    fake = FakeOS(fg_pgrp=1000)
    install(fake)
    xonsh.main._fg_tty_state["acquired"] = True
    xonsh.main._fg_tty_state["tty_fd"] = expected_fd
    xonsh.main._fg_tty_state["old_fg"] = 77
    xonsh.main._release_controlling_terminal()
    # Old fg is back.
    assert ("tcsetpgrp", expected_fd, 77) in fake.calls
    # State was cleared so a second call is a no-op.
    assert xonsh.main._fg_tty_state["acquired"] is False
    assert xonsh.main._fg_tty_state["tty_fd"] == -1
    assert xonsh.main._fg_tty_state["old_fg"] == -1
    # Mask blocked and restored.
    assert len(mask_log) == 2
    assert mask_log[-1][0] == signal.SIG_SETMASK


@skip_if_on_windows
def test_release_swallows_tcsetpgrp_error(monkeypatch, reset_fg_state, fake_tty):
    """Shutdown must not raise when the parent already reclaimed the TTY."""
    install, _, expected_fd = fake_tty
    fake = FakeOS(tcsetpgrp_err=OSError("EPERM"))
    install(fake)
    xonsh.main._fg_tty_state["acquired"] = True
    xonsh.main._fg_tty_state["tty_fd"] = expected_fd
    xonsh.main._fg_tty_state["old_fg"] = 77
    # Must not raise despite tcsetpgrp failing.
    xonsh.main._release_controlling_terminal()
    # State is still cleared.
    assert xonsh.main._fg_tty_state["acquired"] is False


def test_acquire_returns_false_on_windows(monkeypatch, reset_fg_state):
    """POSIX concepts don't apply on Windows — fast no-op."""
    monkeypatch.setattr(xonsh.main, "ON_WINDOWS", True)
    assert xonsh.main._acquire_controlling_terminal() is False


# ---------------------------------------------------------------------------
# _handle_sig_ttin_ttou — livelock guard tests
# ---------------------------------------------------------------------------


@skip_if_on_windows
def test_handle_sig_ttin_ttou_no_op_under_threshold(monkeypatch, reset_fg_state):
    """Below threshold the handler is a pure no-op: counter increments
    but no signal disposition change happens.

    Normal operation fires the handler zero times (xonsh is foreground),
    and legitimate transient bursts — a subprocess briefly stealing
    foreground during a pipeline, a mis-timed tcsetpgrp — should all
    recover well below the threshold without triggering the escalation.
    """
    calls = []

    def fake_signal(sig, handler):
        calls.append((sig, handler))
        return signal.SIG_DFL

    monkeypatch.setattr(xonsh.main.signal, "signal", fake_signal)
    # Fire the handler many times but below threshold.
    threshold = xonsh.main._TTIN_TTOU_LIVELOCK_THRESHOLD
    for _i in range(threshold):
        xonsh.main._handle_sig_ttin_ttou(signal.SIGTTOU, None)
    # Counter reflects all invocations.
    assert xonsh.main._ttin_ttou_counter[0] == threshold
    # But no escalation — signal.signal was never called.
    assert calls == []


@skip_if_on_windows
def test_handle_sig_ttin_ttou_escalates_above_threshold(monkeypatch, reset_fg_state):
    """One firing above threshold → escalate to SIG_IGN.

    This is the livelock guard. If something has been hammering the
    handler (PEP 475 retry on SIGTTIN, PR #6192 application-level
    retry on SIGTTOU), we assume xonsh has lost foreground ownership
    for a reason that won't self-resolve, and we fall back to letting
    the kernel discard the signals outright so the underlying
    syscalls can complete on their next retry.
    """
    calls = []

    def fake_signal(sig, handler):
        calls.append((sig, handler))
        return signal.SIG_DFL

    monkeypatch.setattr(xonsh.main.signal, "signal", fake_signal)
    # One firing past the threshold triggers escalation.
    threshold = xonsh.main._TTIN_TTOU_LIVELOCK_THRESHOLD
    for _i in range(threshold + 1):
        xonsh.main._handle_sig_ttin_ttou(signal.SIGTTOU, None)
    # Two signal.signal calls — one for SIGTTIN, one for SIGTTOU.
    assert len(calls) == 2
    sigs = {sig for sig, _ in calls}
    assert sigs == {signal.SIGTTIN, signal.SIGTTOU}
    for _, handler in calls:
        assert handler is signal.SIG_IGN


@skip_if_on_windows
def test_handle_sig_ttin_ttou_counter_resets_on_setup(
    monkeypatch, reset_fg_state, fake_tty, capture_signal_signal, capture_atexit
):
    """``_setup_controlling_terminal`` must reset the counter so that
    a previous run's escalation does not bleed through into a fresh
    installation.

    Without this reset, a long-lived test process that calls setup
    twice (first triggering escalation, then resetting state) would
    start the second run already at threshold, escalating on the
    first signal instead of providing the full livelock guard.
    """
    # Simulate a prior run that left the counter above threshold.
    xonsh.main._ttin_ttou_counter[0] = xonsh.main._TTIN_TTOU_LIVELOCK_THRESHOLD + 10
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=42)
    install(fake)
    xonsh.main._setup_controlling_terminal()
    # Counter was reset to 0 by _setup_controlling_terminal.
    assert xonsh.main._ttin_ttou_counter[0] == 0


# ---------------------------------------------------------------------------
# _setup_controlling_terminal — orchestration / signal policy tests
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_signal_signal(monkeypatch):
    """Record every ``signal.signal`` call made from ``xonsh.main``.

    Returns the list of ``(sig, handler)`` tuples so tests can assert
    which handlers got installed (Python no-op vs ``SIG_IGN``) without
    actually mutating the real process signal table.
    """
    calls = []

    def fake_signal(sig, handler):
        calls.append((sig, handler))
        # Return a stub "previous handler" — the real signal.signal
        # returns this but callers in xonsh.main don't use it.
        return signal.SIG_DFL

    monkeypatch.setattr(xonsh.main.signal, "signal", fake_signal)
    return calls


@pytest.fixture
def capture_atexit(monkeypatch):
    """Record every ``atexit.register`` call made from ``xonsh.main``.

    Tests use this to verify that the shutdown restorer is registered
    only in the acquire-success case, and not in the fast-path or
    failure paths.
    """
    registered = []

    def fake_register(func, *args, **kwargs):
        registered.append(func)
        return func

    monkeypatch.setattr(xonsh.main.atexit, "register", fake_register)
    return registered


@skip_if_on_windows
def test_setup_non_tty_installs_pyhandler_no_handshake(
    monkeypatch, reset_fg_state, capture_signal_signal, capture_atexit
):
    """Non-TTY stderr skips the handshake but still installs the
    historical Python no-op handlers for ``SIGTTIN`` / ``SIGTTOU``.

    This matches xonsh's pre-handshake behavior: script mode, piped
    input, redirected stderr and test runners (pytest captures stderr
    via a pipe) all land here, and scripts that indirectly touch TTY
    must not be stopped by default ``SIG_DFL``. The handshake and
    atexit restorer are *not* invoked.
    """
    monkeypatch.setattr(xonsh.main.os, "isatty", lambda fd: False)
    xonsh.main._setup_controlling_terminal()
    # Exactly two signal.signal calls — Python no-op handler for each
    # signal, no SIG_IGN follow-up because the handshake never ran.
    assert len(capture_signal_signal) == 2
    installed = {sig for sig, _ in capture_signal_signal}
    assert installed == {signal.SIGTTIN, signal.SIGTTOU}
    for _, handler in capture_signal_signal:
        assert handler is not signal.SIG_IGN
        assert callable(handler)
    assert capture_atexit == []
    # Flag *is* set — we committed to signal handling for this
    # process, and a second call should be a no-op.
    assert xonsh.main._tty_setup_done is True


@skip_if_on_windows
def test_setup_installs_pyhandler_on_acquire_success(
    monkeypatch, reset_fg_state, fake_tty, capture_signal_signal, capture_atexit
):
    """Successful acquire → Python no-op handler + atexit restorer."""
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=42)
    install(fake)
    xonsh.main._setup_controlling_terminal()
    # Idempotency flag set.
    assert xonsh.main._tty_setup_done is True
    # Both signals got a Python callable handler (not SIG_IGN,
    # because we want children to inherit normal dispositions).
    assert len(capture_signal_signal) == 2
    installed_sigs = {sig for sig, _ in capture_signal_signal}
    assert installed_sigs == {signal.SIGTTIN, signal.SIGTTOU}
    for _, handler in capture_signal_signal:
        assert handler is not signal.SIG_IGN
        assert callable(handler)
    # Shutdown restorer is registered.
    assert xonsh.main._release_controlling_terminal in capture_atexit


@skip_if_on_windows
def test_setup_installs_sigign_on_acquire_failure(
    monkeypatch, reset_fg_state, fake_tty, capture_signal_signal, capture_atexit
):
    """Acquire failure → SIG_IGN replaces the step-1 Python handlers.

    This is the sandbox path. ``_setup_controlling_terminal`` first
    installs a Python no-op handler (step 1, unconditional) and then
    *replaces* it with ``SIG_IGN`` when the handshake cannot make
    xonsh foreground. The replacement is what prevents asyncio from
    drowning in ``SIGTT*`` wakeups — ``SIG_IGN`` drops the signals at
    the kernel boundary before they ever reach Python.
    """
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(fg_pgrp=42, tcsetpgrp_err=OSError("EPERM"))
    install(fake)
    xonsh.main._setup_controlling_terminal()
    assert xonsh.main._tty_setup_done is True
    # Four signal.signal calls total: two Python no-op handlers from
    # step 1, then two SIG_IGN replacements from the failure path.
    assert len(capture_signal_signal) == 4
    # Step 1: Python no-op handler for each signal.
    step1 = capture_signal_signal[:2]
    step1_sigs = {sig for sig, _ in step1}
    assert step1_sigs == {signal.SIGTTIN, signal.SIGTTOU}
    for _, handler in step1:
        assert handler is not signal.SIG_IGN
        assert callable(handler)
    # Step 2: SIG_IGN replacement.
    step2 = capture_signal_signal[2:]
    step2_sigs = {sig for sig, _ in step2}
    assert step2_sigs == {signal.SIGTTIN, signal.SIGTTOU}
    for _, handler in step2:
        assert handler is signal.SIG_IGN
    # Final state per signal is SIG_IGN (last write wins).
    last_per_sig = {}
    for sig, handler in capture_signal_signal:
        last_per_sig[sig] = handler
    assert last_per_sig[signal.SIGTTIN] is signal.SIG_IGN
    assert last_per_sig[signal.SIGTTOU] is signal.SIG_IGN
    # No atexit — nothing was acquired to release.
    assert capture_atexit == []


@skip_if_on_windows
def test_setup_does_not_register_atexit_on_fast_path(
    monkeypatch, reset_fg_state, fake_tty, capture_signal_signal, capture_atexit
):
    """Already-foreground fast path must not schedule a restorer.

    If xonsh was launched by a well-behaved shell that already put it
    in the foreground group, the handshake short-circuits. Registering
    a restorer in that case would race with the parent shell's own
    ``tcsetpgrp`` on exit and is a bug.
    """
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=999)  # already fg
    install(fake)
    xonsh.main._setup_controlling_terminal()
    # Python handler still installed as a safety net.
    assert len(capture_signal_signal) == 2
    for _, handler in capture_signal_signal:
        assert handler is not signal.SIG_IGN
    # But NO atexit — this is the key distinction from the
    # acquire-success path.
    assert capture_atexit == []


@skip_if_on_windows
def test_setup_is_idempotent(
    monkeypatch, reset_fg_state, fake_tty, capture_signal_signal, capture_atexit
):
    """A second call does nothing. This is what makes it safe to call
    from both :func:`main` and :func:`main_xonsh`."""
    install, _, _ = fake_tty
    monkeypatch.delenv("XONSH_NO_FG_TAKEOVER", raising=False)
    fake = FakeOS(pid=1000, pgid=999, sid=500, fg_pgrp=42)
    install(fake)
    xonsh.main._setup_controlling_terminal()
    first_call_count = len(capture_signal_signal)
    first_atexit_count = len(capture_atexit)
    # Second call
    xonsh.main._setup_controlling_terminal()
    assert len(capture_signal_signal) == first_call_count
    assert len(capture_atexit) == first_atexit_count


def test_setup_is_noop_on_windows(
    monkeypatch, reset_fg_state, capture_signal_signal, capture_atexit
):
    """POSIX concepts don't apply on Windows — no handlers installed."""
    monkeypatch.setattr(xonsh.main, "ON_WINDOWS", True)
    xonsh.main._setup_controlling_terminal()
    assert capture_signal_signal == []
    assert capture_atexit == []
    assert xonsh.main._tty_setup_done is False
