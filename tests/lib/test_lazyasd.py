"""Tests lazy and self destruictive objects."""

import threading

from xonsh.lib.lazyasd import LazyDict, LazyObject

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


#
# LazyDict Tests
#


def test_lazydict_iter_preserves_insertion_order():
    """Iteration yields keys in insertion order on a fresh LazyDict
    (not hash-randomized). Required for pytest-xdist: collection happens
    before any lazy load, so worker processes must see the same sequence.
    """
    loaders = {chr(c): (lambda c=c: c) for c in range(97, 123)}
    ld = LazyDict(loaders, {}, "ld")
    assert list(ld) == list(loaders)


def test_lazydict_iter_stable_after_partial_load():
    """After partial lazy loads, iteration is still deterministic and
    repeatable — important so iteration-based callers don't see flicker.
    """
    loaders = {chr(c): (lambda c=c: c) for c in range(97, 123)}
    expected_keys = set(loaders)
    ld = LazyDict(loaders, {}, "ld")
    _ = ld["a"]
    _ = ld["m"]
    _ = ld["z"]
    first = list(ld)
    assert set(first) == expected_keys
    assert list(ld) == first
