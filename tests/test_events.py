"""Event tests"""
from xonsh.events import Events

def test_calling():
    e = Events()
    e.on_test.__doc__ = "Test event"

    called = False
    @e.on_test
    def _(spam):
        nonlocal called
        called = spam

    e.on_test.fire("eggs")

    assert called == "eggs"

def test_until_true():
    e = Events()
    e.on_test.__doc__ = "Test event"

    called = 0

    @e.test
    def on_test():
        nonlocal called
        called += 1
        return True

    @e.on_test
    def second():
        nonlocal called
        called += 1
        return True

    e.on_test.until_true()

    assert called == 1

def test_until_false():
    e = Events()
    e.on_test.__doc__ = "Test event"

    called = 0

    @e.on_test
    def first():
        nonlocal called
        called += 1
        return False

    @e.on_test
    def second():
        nonlocal called
        called += 1
        return False

    e.on_test.until_false()

    assert called == 1

def test_validator():
    e = Events()
    e.on_test.__doc__ = "Test event"

    called = 0

    @e.on_test
    def first(n):
        nonlocal called
        called += 1
        return False

    @first.validator
    def v(n):
        return n == 'spam'

    @e.on_test
    def second(n):
        nonlocal called
        called += 1
        return False

    e.on_test.fire('egg')
    assert called == 1

    called = 0
    e.on_test.fire('spam')
    assert called == 2
