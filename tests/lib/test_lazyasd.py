"""Tests lazy and self destruictive objects."""

import threading

from xonsh.lib.lazyasd import LazyObject

#
# LazyObject Tests
#


def test_lazyobject_getitem():
    lo = LazyObject(lambda: {"x": 1}, {}, "lo")
    assert 1 == lo["x"]


def test_lazyobject_thread_safe_single_init():
    """Loader must be called exactly once even under concurrent access."""
    call_count = 0
    lock = threading.Lock()
    barrier = threading.Barrier(20)

    def load():
        nonlocal call_count
        with lock:
            call_count += 1
        return 42

    ctx = {}
    lo = LazyObject(load, ctx, "lo")

    results = []

    def access():
        barrier.wait()  # all threads start together
        results.append(str(lo))

    threads = [threading.Thread(target=access) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert call_count == 1
    assert ctx["lo"] == 42
    assert all(r == "42" for r in results)
