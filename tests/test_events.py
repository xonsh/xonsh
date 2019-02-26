"""Event tests"""
import inspect
import pytest
from xonsh.events import EventManager, Event, LoadEvent


@pytest.fixture
def events():
    return EventManager()


def test_event_calling(events):
    called = False

    @events.on_test
    def _(spam, **_):
        nonlocal called
        called = spam

    events.on_test.fire(spam="eggs")

    assert called == "eggs"


def test_event_returns(events):
    called = 0

    @events.on_test
    def on_test(**_):
        nonlocal called
        called += 1
        return 1

    @events.on_test
    def second(**_):
        nonlocal called
        called += 1
        return 2

    vals = events.on_test.fire()

    assert called == 2
    assert set(vals) == {1, 2}


def test_validator(events):
    called = None

    @events.on_test
    def first(n, **_):
        nonlocal called
        called += 1
        return False

    @first.validator
    def v(n):
        return n == "spam"

    @events.on_test
    def second(n, **_):
        nonlocal called
        called += 1
        return False

    called = 0
    events.on_test.fire(n="egg")
    assert called == 1

    called = 0
    events.on_test.fire(n="spam")
    assert called == 2


def test_eventdoc(events):
    docstring = "Test event"
    events.doc("on_test", docstring)

    assert inspect.getdoc(events.on_test) == docstring


def test_transmogrify(events):
    docstring = "Test event"
    events.doc("on_test", docstring)

    @events.on_test
    def func(**_):
        pass

    assert isinstance(events.on_test, Event)
    assert len(events.on_test) == 1
    assert inspect.getdoc(events.on_test) == docstring

    events.transmogrify("on_test", LoadEvent)

    assert isinstance(events.on_test, LoadEvent)
    assert len(events.on_test) == 1
    assert inspect.getdoc(events.on_test) == docstring


def test_transmogrify_by_string(events):
    docstring = "Test event"
    events.doc("on_test", docstring)

    @events.on_test
    def func(**_):
        pass

    assert isinstance(events.on_test, Event)
    assert len(events.on_test) == 1
    assert inspect.getdoc(events.on_test) == docstring

    events.transmogrify("on_test", "LoadEvent")

    assert isinstance(events.on_test, LoadEvent)
    assert len(events.on_test) == 1
    assert inspect.getdoc(events.on_test) == docstring


def test_load(events):
    events.transmogrify("on_test", "LoadEvent")
    called = 0

    @events.on_test
    def on_test(**_):
        nonlocal called
        called += 1

    assert called == 0

    events.on_test.fire()
    assert called == 1

    @events.on_test
    def second(**_):
        nonlocal called
        called += 1

    assert called == 2


def test_load_2nd_call(events):
    events.transmogrify("on_test", "LoadEvent")
    called = 0

    @events.on_test
    def on_test(**_):
        nonlocal called
        called += 1

    assert called == 0

    events.on_test.fire()
    assert called == 1

    events.on_test.fire()
    assert called == 1


def test_typos(xonsh_builtins):
    for name, ev in vars(xonsh_builtins.events).items():
        if "pytest" in name:
            continue
        assert inspect.getdoc(ev)


def test_exists(events):
    events.doc("on_test", "Test event")
    assert events.exists("on_test")
    assert not events.exists("on_best")
