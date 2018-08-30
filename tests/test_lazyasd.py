"""Tests lazy and self destruictive objects."""
from xonsh.lazyasd import LazyObject

#
# LazyObject Tests
#


def test_lazyobject_getitem():
    lo = LazyObject(lambda: {"x": 1}, {}, "lo")
    assert 1 == lo["x"]
