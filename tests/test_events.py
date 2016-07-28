"""Event tests"""
from xonsh.events import Events

def test_calling():
    e = Events()
    e.test.__doc__ = "Test event"

    called = False
    @e.test.handler
    def _(spam):
        nonlocal called
        called = spam

    e.test("eggs")

    assert called == "eggs"

def test_untilTrue():
    e = Events()
    e.test.__doc__ = "Test event"

    called = 0

    @e.test.handler
    def first():
        nonlocal called
        called += 1
        return True

    @e.test.handler
    def second():
        nonlocal called
        called += 1
        return True

    e.test.untilTrue()

    assert called == 1

def test_untilFalse():
    e = Events()
    e.test.__doc__ = "Test event"

    called = 0

    @e.test.handler
    def first():
        nonlocal called
        called += 1
        return False

    @e.test.handler
    def second():
        nonlocal called
        called += 1
        return False

    e.test.untilFalse()

    assert called == 1

def test_loopback():
    e = Events()
    e.test.__doc__ = "Test event"

    @e.test.handler
    def first(num):
        return num + 1

    @e.test.handler
    def second(num):
        return num + 1

    rv = e.test.loopback(0)

    assert rv == 2

