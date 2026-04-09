import io
import os
import sys
from unittest.mock import patch

from xonsh.procs.proxies import ProcProxy, ProcProxyThread

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_fake_spec(**overrides):
    defaults = dict(
        last_in_pipeline=False,
        captured_stdout=None,
        captured_stderr=None,
        pipe_channels=[],
        stack=None,
    )
    defaults.update(overrides)
    return type("FakeSpec", (), defaults)()


def _make_proc_proxy(f, xession, stdin=None, stdout=None, stderr=None):
    """Create a ProcProxy with a fake spec already attached."""
    p = ProcProxy(f=f, args=[], stdin=stdin, stdout=stdout, stderr=stderr, env={})
    p.spec = _make_fake_spec()
    return p


def _fd_is_open(fd):
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


# ── still_writable: fd=-1 must not mask real errors ──────────────────────


def test_still_writable_negative_fd_returns_true():
    """fd=-1 means no pipe — treat as writable so OSError is not masked."""
    assert still_writable(-1) is True


def test_still_writable_closed_fd_returns_false():
    """A closed fd should return False (pipe broken by downstream)."""
    r, w = os.pipe()
    os.close(w)
    assert still_writable(w) is False
    os.close(r)


def test_still_writable_open_fd_returns_true():
    """An open writable fd should return True."""
    r, w = os.pipe()
    assert still_writable(w) is True
    os.close(r)
    os.close(w)


def test_proc_proxy_thread_oserror_not_masked_without_pipe(xession):
    """Alias raising OSError without piped stdout must return 1, not 0."""
    with patch.object(ProcProxyThread, "start"):
        p = ProcProxyThread(
            f=lambda: (_ for _ in ()).throw(OSError("real error")),
            args=[],
            stdin=None,
            stdout=None,
            stderr=None,
            env={},
        )
    p.spec = _make_fake_spec()
    # c2pwrite and errwrite are -1 (no pipe)
    assert p.c2pwrite == -1
    assert p.errwrite == -1

    p.run()

    assert p.returncode == 1, (
        f"expected returncode=1 for real OSError, got {p.returncode}"
    )


# ── ProcProxyThread: devnull leak on f=None ──────────────────────────────


def test_close_devnull_called_when_f_is_none(xession):
    """_close_devnull must be called even when f is None (early return)."""
    with patch.object(ProcProxyThread, "start"):
        p = ProcProxyThread(
            f=None,
            args=[],
            stdin=None,
            stdout=None,
            stderr=None,
        )

    p._devnull = os.open(os.devnull, os.O_RDWR)
    devnull_fd = p._devnull

    p.run()

    assert not hasattr(p, "_devnull"), "_devnull attr should be deleted"
    assert not _fd_is_open(devnull_fd), f"fd {devnull_fd} should be closed"


# ── ProcProxy.wait(): explicit fd cleanup ────────────────────────────────


class TestProcProxyWaitFdCleanup:
    """ProcProxy.wait() must explicitly close file handles it creates."""

    def test_stdin_int_fd_explicitly_closed(self, xession):
        """stdin as int fd → safe_fdclose called on the wrapper."""
        r, w = os.pipe()
        os.write(w, b"hello")
        os.close(w)

        def alias(stdin):
            stdin.read()

        p = _make_proc_proxy(alias, xession, stdin=r)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            # At least one call should be a TextIOWrapper wrapping our fd
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert any(isinstance(h, io.TextIOWrapper) for h in closed_handles), (
                f"expected TextIOWrapper in closed handles, got {closed_handles}"
            )

    def test_stdout_int_fd_explicitly_closed(self, xession):
        """stdout as int fd >= 3 → safe_fdclose called on the wrapper."""
        r, w = os.pipe()

        def alias(stdout):
            stdout.write("hi")

        p = _make_proc_proxy(alias, xession, stdout=w)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert any(isinstance(h, io.TextIOWrapper) for h in closed_handles), (
                f"expected TextIOWrapper in closed handles, got {closed_handles}"
            )
        os.close(r)

    def test_stderr_int_fd_explicitly_closed(self, xession):
        """stderr as int fd >= 3 → safe_fdclose called on the wrapper."""
        r, w = os.pipe()

        def alias(stderr):
            stderr.write("err")

        p = _make_proc_proxy(alias, xession, stderr=w)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert any(isinstance(h, io.TextIOWrapper) for h in closed_handles), (
                f"expected TextIOWrapper in closed handles, got {closed_handles}"
            )
        os.close(r)

    def test_sys_stdout_not_in_owned(self, xession):
        """stdout=None uses sys.stdout — must NOT be passed to safe_fdclose."""

        def alias():
            pass

        p = _make_proc_proxy(alias, xession)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert sys.stdout not in closed_handles
            assert sys.stderr not in closed_handles

    def test_filelike_stdout_not_in_owned(self, xession):
        """stdout as file-like we don't own — must NOT be in safe_fdclose."""
        buf = io.StringIO()

        def alias(stdout):
            stdout.write("hi")

        p = _make_proc_proxy(alias, xession, stdout=buf)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert buf not in closed_handles

    def test_fd_closed_even_on_exception(self, xession):
        """Owned handles closed even when the alias raises."""
        r, w = os.pipe()

        def alias(stdout):
            raise RuntimeError("boom")

        p = _make_proc_proxy(alias, xession, stdout=w)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            assert p.returncode == 1
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            assert any(isinstance(h, io.TextIOWrapper) for h in closed_handles), (
                "owned stdout must be closed despite exception"
            )
        os.close(r)

    def test_all_three_fds_explicitly_closed(self, xession):
        """stdin + stdout + stderr all as int fds — all explicitly closed."""
        in_r, in_w = os.pipe()
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        os.write(in_w, b"data")
        os.close(in_w)

        def alias(stdin, stdout, stderr):
            stdout.write(stdin.read())

        p = _make_proc_proxy(alias, xession, stdin=in_r, stdout=out_w, stderr=err_w)
        with patch("xonsh.procs.proxies.safe_fdclose") as mock_close:
            p.wait()
            closed_handles = [c.args[0] for c in mock_close.call_args_list]
            wrappers = [h for h in closed_handles if isinstance(h, io.TextIOWrapper)]
            assert len(wrappers) == 3, (
                f"expected 3 TextIOWrappers closed, got {len(wrappers)}"
            )
        os.close(out_r)
        os.close(err_r)
