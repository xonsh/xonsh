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

def test_until_true():
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

    e.test.until_true()

    assert called == 1

def test_until_false():
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

    e.test.until_false()

    assert called == 1

def test_validator():
    e = Events()
    e.test.__doc__ = "Test event"

    called = 0

    @e.test.handler
    def first(n):
        nonlocal called
        called += 1
        return False

    @first.validator
    def v(n):
        return n == 'spam'

    @e.test.handler
    def second(n):
        nonlocal called
        called += 1
        return False

    e.test('egg')
    assert called == 1

    called = 0
    e.test('spam')
    assert called == 2
