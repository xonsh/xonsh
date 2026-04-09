import os
from unittest.mock import patch

from xonsh.procs.proxies import ProcProxyThread


def test_close_devnull_called_when_f_is_none(xession):
    """When f is None, run() returns early but must still close devnull fd."""
    # Build the object without starting the thread
    with patch.object(ProcProxyThread, "start"):
        p = ProcProxyThread(
            f=None,
            args=[],
            stdin=None,
            stdout=None,
            stderr=None,
        )

    # Simulate that _get_handles opened devnull (as with subprocess.DEVNULL)
    p._devnull = os.open(os.devnull, os.O_RDWR)
    devnull_fd = p._devnull

    # Call run() directly — the early return path
    p.run()

    assert not hasattr(p, "_devnull"), "_devnull attr should be deleted"
    try:
        os.fstat(devnull_fd)
        assert False, f"fd {devnull_fd} should have been closed"
    except OSError:
        pass  # expected — fd is closed
