"""
Events for xonsh.

In all likelihood, you want builtins.events

The best way to "declare" an event is something like::

    events.doc('on_spam', "Comes with eggs")
"""
import abc
import collections.abc

from xonsh.tools import print_exception


class AbstractEvent(collections.abc.MutableSet, abc.ABC):
    """
    A given event that handlers can register against.

    Acts as a ``MutableSet`` for registered handlers.

    Note that ordering is never guaranteed.
    """
    def __call__(self, handler):
        """
        Registers a handler. It's suggested to use this as a decorator.

        A decorator method is added to the handler, validator(). If a validator
        function is added, it can filter if the handler will be considered. The
        validator takes the same arguments as the handler. If it returns False,
        the handler will not called or considered, as if it was not registered
        at all.

        Parameters
        ----------
        handler : callable
            The handler to register

        Returns
        -------
        rtn : callable
            The handler
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

    def _filterhandlers(self, handlers, *pargs, **kwargs):
        """
        Helper method for implementing classes. Generates the handlers that pass validation.
        """
        for handler in handlers:
            if handler.__validator is not None and not handler.__validator(*pargs, **kwargs):
                continue
            yield handler

    @abc.abstractmethod
    def fire(self, *pargs, **kwargs):
        """
        Fires an event, calling registered handlers with the given arguments.

        Parameters
        ----------
        *pargs :
            Positional arguments to pass to each handler
        **kwargs :
            Keyword arguments to pass to each handler
        """


class Event(AbstractEvent):
    """
    An event species for notify and scatter-gather events.
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
        """
        Add an element to a set.

        This has no effect if the element is already present.
        """
        self._handlers.add(item)

    def discard(self, item):
        """
        Remove an element from a set if it is a member.

        If the element is not a member, do nothing.
        """
        self._handlers.discard(item)

    def fire(self, *pargs, **kwargs):
        """
        Fires an event, calling registered handlers with the given arguments. A non-unique iterable
        of the results is returned.

        Each handler is called immediately. Exceptions are turned in to warnings.

        Parameters
        ----------
        *pargs :
            Positional arguments to pass to each handler
        **kwargs :
            Keyword arguments to pass to each handler

        Returns
        -------
        vals : iterable
            Return values of each handler. If multiple handlers return the same value, it will
            appear multiple times.
        """
        vals = []
        for handler in self._filterhandlers(self._handlers, *pargs, **kwargs):
            try:
                rv = handler(*pargs, **kwargs)
            except Exception:
                print_exception("Exception raised in event handler; ignored.")
            else:
                vals.append(rv)
        return vals


class LoadEvent(AbstractEvent):
    """
    An event species where each handler is called exactly once, shortly after either the event is
    fired or the handler is registered (whichever is later). Additional firings are ignored.

    Note: Does not support scatter/gather, due to never knowing when we have all the handlers.

    Note: Maintains a strong reference to pargs/kwargs in case of the addition of future handlers.

    Note: This is currently NOT thread safe.
    """
    def __init__(self):
        self._fired = set()
        self._unfired = set()
        self._hasfired = False

    def __len__(self):
        return len(self._fired) + len(self._unfired)

    def __contains__(self, item):
        return item in self._fired or item in self._unfired

    def __iter__(self):
        yield from self._fired
        yield from self._unfired

    def add(self, item):
        """
        Add an element to a set.

        This has no effect if the element is already present.
        """
        if self._hasfired:
            self._call(item)
            self._fired.add(item)
        else:
            self._unfired.add(item)

    def discard(self, item):
        """
        Remove an element from a set if it is a member.

        If the element is not a member, do nothing.
        """
        self._fired.discard(item)
        self._unfired.discard(item)

    def _call(self, handler):
        try:
            handler(*self._pargs, **self._kwargs)
        except Exception:
            print_exception("Exception raised in event handler; ignored.")

    def fire(self, *pargs, **kwargs):
        if self._hasfired:
            return
        self._pargs = pargs
        self._kwargs = kwargs
        while self._unfired:
            handler = self._unfired.pop()
            self._call(handler)
        self._hasfired = True
        return ()  # Entirely for API compatibility


class EventManager:
    """
    Container for all events in a system.

    Meant to be a singleton, but doesn't enforce that itself.

    Each event is just an attribute. They're created dynamically on first use.
    """

    def doc(self, name, docstring):
        """
        Applies a docstring to an event.

        Parameters
        ----------
        name : str
            The name of the event, eg "on_precommand"
        docstring : str
            The docstring to apply to the event
        """
        type(getattr(self, name)).__doc__ = docstring

    def transmogrify(self, name, klass):
        """
        Converts an event from one species to another, preserving handlers and docstring.

        Please note: Some species maintain specialized state. This is lost on transmogrification.

        Parameters
        ----------
        name : str
            The name of the event, eg "on_precommand"
        klass : sublcass of AbstractEvent
            The type to turn the event in to.
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
        """Get an event, if it doesn't already exist."""
        # This is only called if the attribute doesn't exist, so create the Event...
        # (A little bit of magic to enable docstrings to work right)
        e = type(name, (Event,), {'__doc__': None})()
        # ... and save it.
        setattr(self, name, e)
        # Now it exists, and we won't be called again.
        return e


# Not lazy because:
# 1. Initialization of EventManager can't be much cheaper
# 2. It's expected to be used at load time, negating any benefits of using lazy object
events = EventManager()
