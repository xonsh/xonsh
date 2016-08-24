"""
Events for xonsh.

In all likelihood, you want builtins.__xonsh_events__

The best way to "declare" an event is something like::

    __xonsh_events__.on_spam.doc("Comes with eggs")
"""
import abc
import collections.abc
import traceback
import sys


class AbstractEvent(collections.abc.MutableSet, abc.ABC):
    def __call__(self, handler):
        """
        Registers a handler. It's suggested to use this as a decorator.

        A decorator method is added to the handler, validator(). If a validator
        function is added, it can filter if the handler will be considered. The
        validator takes the same arguments as the handler. If it returns False,
        the handler will not called or considered, as if it was not registered
        at all.
        """
        #  Using Pythons "private" munging to minimize hypothetical collisions
        handler.__validator = None
        self.add(handler)

        def validator(vfunc):
            """
            Adds a validator function to a handler to limit when it is considered.
            """
            handler.__validator = vfunc
        handler.validator = validator

        return handler

    def _filterhandlers(self, *pargs, **kwargs):
        """
        Helper method for implementing classes. Generates the handlers that pass validation.
        """
        for handler in self:
            if handler.__validator is not None and not handler.__validator(*pargs, **kwargs):
                continue
            yield handler

    @abc.abstractmethod
    def fire(self, *pargs, **kwargs):
        """
        Fires an event, calling registered handlers with the given arguments.
        """


class Event(AbstractEvent):
    """
    A given event that handlers can register against.

    Acts as a ``set`` for registered handlers.

    Note that ordering is never guaranteed.
    """
    # Wish I could just pull from set...
    def __init__(self):
        self._handlers = set()

    def __len__(self):
        return len(self._handlers)

    def __contains__(self, item):
        return item in self._handlers

    def __iter__(self):
        yield from self._handlers

    def add(self, item):
        return self._handlers.add(item)

    def discard(self, item):
        return self._handlers.discard(item)

    def fire(self, *pargs, **kwargs):
        """
        Fires each event, returning a non-unique iterable of the results.
        """
        vals = []
        for handler in self._filterhandlers(*pargs, **kwargs):
            try:
                rv = handler(*pargs, **kwargs)
            except Exception:
                print("Exception raised in event handler; ignored.", file=sys.stderr)
                traceback.print_exc()
            else:
                vals.append(rv)
        return vals


class LoadEvent(AbstractEvent):
    """
    A kind of event in which each handler is called exactly once.
    """
    def __init__(self):
        self._handlers = set()

    def __len__(self):
        return len(self._handlers)

    def __contains__(self, item):
        return item in self._handlers

    def __iter__(self):
        yield from self._handlers

    def add(self, item):
        return self._handlers.add(item)

    def discard(self, item):
        return self._handlers.discard(item)

    def fire(self, *pargs, **kwargs):
        raise NotImplementedError("See #1550")


class EventManager:
    """
    Container for all events in a system.

    Meant to be a singleton, but doesn't enforce that itself.

    Each event is just an attribute. They're created dynamically on first use.
    """

    def doc(self, name, docstring):
        """
        Applies a docstring to an event.
        """
        type(getattr(self, name)).__doc__ = docstring

    def transmogrify(self, name, klass):
        """
        Converts an event from one species to another.

        Please note: Some species may do special things with handlers. This is lost.
        """
        if isinstance(klass, str):
            klass = globals()[klass]

        if not issubclass(klass, AbstractEvent):
            raise ValueError("Invalid event class; must be a subclass of AbstractEvent")

        oldevent = getattr(self, name)
        newevent = type(name, (klass,), {'__doc__': type(oldevent).__doc__})()
        setattr(self, name, newevent)

        for handler in oldevent:
            newevent.add(handler)

    def __getattr__(self, name):
        e = type(name, (Event,), {'__doc__': None})()
        setattr(self, name, e)
        return e


events = EventManager()
