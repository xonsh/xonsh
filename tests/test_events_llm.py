"""Tests for reload-safe event handler uniqueness (xonsh/xonsh#3276)."""

import pytest

from xonsh.events import EventManager, LoadEvent, _handler_key


@pytest.fixture
def events():
    return EventManager()


# --- _handler_key ---


def _module_level_handler(**kw):
    pass


def test_handler_key_named_function():
    """Named module-level functions use (module, qualname) as key."""
    key = _handler_key(_module_level_handler)
    assert key == (
        _module_level_handler.__module__,
        _module_level_handler.__qualname__,
    )
    assert "<" not in _module_level_handler.__qualname__


def test_handler_key_closure():
    """Closures (with '<locals>' in qualname) fall back to id()."""

    def make():
        def inner(**kw):
            pass

        return inner

    h = make()
    assert "<" in h.__qualname__
    assert _handler_key(h) == id(h)


def test_handler_key_lambda():
    """Lambdas fall back to id()."""
    h = lambda **kw: None  # noqa: E731
    assert "<" in h.__qualname__
    assert _handler_key(h) == id(h)


def test_handler_key_bound_method():
    """Bound methods fall back to id()."""

    class C:
        def method(self, **kw):
            pass

    m = C().method
    assert _handler_key(m) == id(m)


def test_handler_key_two_bound_methods_differ():
    """Two bound methods from different instances are distinct."""

    class C:
        def method(self, **kw):
            pass

    assert _handler_key(C().method) != _handler_key(C().method)


# --- Event reload-safety ---


def test_named_handler_replaced_on_reregister(events):
    """Re-registering a handler with the same module+qualname replaces it."""

    def handler(**kw):
        return "old"

    handler.__module__ = "my_mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    def handler(**kw):  # noqa: F811
        return "new"

    handler.__module__ = "my_mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    assert len(events.on_test) == 1
    assert events.on_test.fire() == ["new"]


def test_closures_not_collapsed(events):
    """Two closures registered on the same event stay separate."""

    def make(val):
        def inner(**kw):
            return val

        return inner

    events.on_test(make("a"))
    events.on_test(make("b"))

    assert len(events.on_test) == 2
    assert set(events.on_test.fire()) == {"a", "b"}


def test_discard_by_qualname(events):
    """Discard finds the handler by key, not by identity."""

    def handler(**kw):
        pass

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)
    assert len(events.on_test) == 1

    # New object, same key
    def handler(**kw):  # noqa: F811
        pass

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test.discard(handler)
    assert len(events.on_test) == 0


def test_contains_by_qualname(events):
    """__contains__ matches by key, not by identity."""

    def handler(**kw):
        pass

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    # Different object, same key
    def handler2(**kw):
        pass

    handler2.__module__ = "mod"
    handler2.__qualname__ = "handler"
    assert handler2 in events.on_test


# --- LoadEvent reload-safety ---


def test_load_event_replaces_on_reregister(events):
    """LoadEvent also replaces handlers with the same key."""
    events.transmogrify("on_test", LoadEvent)

    def handler(**kw):
        return "old"

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    def handler(**kw):  # noqa: F811
        return "new"

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    assert len(events.on_test) == 1


def test_load_event_fires_replaced_handler(events):
    """After replace + fire, only the new handler runs."""
    events.transmogrify("on_test", LoadEvent)
    called = []

    def handler(**kw):
        called.append("old")

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    def handler(**kw):  # noqa: F811
        called.append("new")

    handler.__module__ = "mod"
    handler.__qualname__ = "handler"
    events.on_test(handler)

    events.on_test.fire()
    assert called == ["new"]


# --- Delayed add/discard during fire ---


def test_delayed_add_replaces_during_fire(events):
    """Handler added during fire replaces by key on next fire."""

    def adder(**kw):
        # Registering a handler with the same key as 'target' during fire
        def target(**kw):
            return "replaced"

        target.__module__ = "mod"
        target.__qualname__ = "target"
        events.on_test(target)

    def target(**kw):
        return "original"

    target.__module__ = "mod"
    target.__qualname__ = "target"

    events.on_test(adder)
    events.on_test(target)

    events.on_test.fire()  # adder runs, schedules replacement
    vals = events.on_test.fire()
    assert "replaced" in vals
    assert "original" not in vals


def test_delayed_discard_by_key_during_fire(events):
    """Discard during fire uses key matching."""
    removed = False

    def remover(**kw):
        nonlocal removed
        if not removed:
            removed = True

            # Create a new object with same key to discard
            def target(**kw):
                pass

            target.__module__ = "mod"
            target.__qualname__ = "target"
            events.on_test.discard(target)

    def target(**kw):
        return "target"

    target.__module__ = "mod"
    target.__qualname__ = "target"

    events.on_test(remover)
    events.on_test(target)

    events.on_test.fire()  # remover schedules discard
    vals = events.on_test.fire()
    assert "target" not in vals
