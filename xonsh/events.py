"""
Events for xonsh.

In all likelihood, you want xonsh.built_ins.XSH.events

The best way to "declare" an event is something like::

    events.doc('on_spam', "Comes with eggs")
"""
import abc
import collections.abc
import inspect

from xonsh.built_ins import XSH
from xonsh.tools import print_exception


def has_kwargs(func):
    return any(
        p.kind == p.VAR_KEYWORD for p in inspect.signature(func).parameters.values()
    )


def debug_level():
    if XSH.env:
        return XSH.env.get("XONSH_DEBUG")
    # FIXME: Under pytest, return 1(?)
    else:
        return 0  # Optimize for speed, not guaranteed correctness


class AbstractEvent(collections.abc.MutableSet, abc.ABC):
    """
    A given event that handlers can register against.

    Acts as a ``MutableSet`` for registered handlers.

    Note that ordering is never guaranteed.
    """

    @property
    def species(self):
        """
        The species (basically, class) of the event
        """
        return type(self).__bases__[
            0
        ]  # events.on_chdir -> <class on_chdir> -> <class Event>

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
        #  Using Python's "private" munging to minimize hypothetical collisions
        handler.__validator = None
        if debug_level():
            if not has_kwargs(handler):
                raise ValueError("Event handlers need a **kwargs for future proofing")
        self.add(handler)

        def validator(vfunc):
            """
            Adds a validator function to a handler to limit when it is considered.
            """
            if debug_level():
                if not has_kwargs(handler):
                    raise ValueError(
                        "Event validators need a **kwargs for future proofing"
                    )
            handler.__validator = vfunc

        handler.validator = validator

        return handler

    def _filterhandlers(self, handlers, **kwargs):
        """
        Helper method for implementing classes. Generates the handlers that pass validation.
        """
        for handler in handlers:
            if handler.__validator is not None and not handler.__validator(**kwargs):
                continue
            yield handler

    @abc.abstractmethod
    def fire(self, **kwargs):
        """
        Fires an event, calling registered handlers with the given arguments.

        Parameters
        ----------
        **kwargs
            Keyword arguments to pass to each handler
        """


class Event(AbstractEvent):
    """
    An event species for notify and scatter-gather events.
    """

    # Wish I could just pull from set...
    def __init__(self):
        self._handlers = set()
        self._firing = False
        self._delayed_adds = None
        self._delayed_discards = None

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
        if self._firing:
            if self._delayed_adds is None:
                self._delayed_adds = set()
            self._delayed_adds.add(item)
        else:
            self._handlers.add(item)

    def discard(self, item):
        """
        Remove an element from a set if it is a member.

        If the element is not a member, do nothing.
        """
        if self._firing:
            if self._delayed_discards is None:
                self._delayed_discards = set()
            self._delayed_discards.add(item)
        else:
            self._handlers.discard(item)

    def fire(self, **kwargs):
        """
        Fires an event, calling registered handlers with the given arguments. A non-unique iterable
        of the results is returned.

        Each handler is called immediately. Exceptions are turned in to warnings.

        Parameters
        ----------
        **kwargs
            Keyword arguments to pass to each handler

        Returns
        -------
        vals : iterable
            Return values of each handler. If multiple handlers return the same value, it will
            appear multiple times.
        """
        vals = []
        self._firing = True
        for handler in self._filterhandlers(self._handlers, **kwargs):
            try:
                rv = handler(**kwargs)
            except Exception:
                print_exception("Exception raised in event handler; ignored.")
            else:
                vals.append(rv)
        # clean up
        self._firing = False
        if self._delayed_adds is not None:
            self._handlers.update(self._delayed_adds)
            self._delayed_adds = None
        if self._delayed_discards is not None:
            self._handlers.difference_update(self._delayed_discards)
            self._delayed_discards = None
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
            handler(**self._kwargs)
        except Exception:
            print_exception("Exception raised in event handler; ignored.")

    def fire(self, **kwargs):
        if self._hasfired:
            return
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

    def register(self, func):
        """
            wraps ``EventManager.doc``

        Parameters
        ----------
        func
            extract name and doc from the function
        """

        name = func.__name__
        doc = inspect.getdoc(func)
        sign = inspect.signature(func)
        return self.doc(name, f"{name}{sign}\n\n{doc}")

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

    @staticmethod
    def _mkevent(name, species=Event, doc=None):
        # NOTE: Also used in `xonsh_events` test fixture
        # (A little bit of magic to enable docstrings to work right)
        return type(
            name,
            (species,),
            {
                "__doc__": doc,
                "__module__": "xonsh.events",
                "__qualname__": "events." + name,
            },
        )()

    def transmogrify(self, name, species):
        """
        Converts an event from one species to another, preserving handlers and docstring.

        Please note: Some species maintain specialized state. This is lost on transmogrification.

        Parameters
        ----------
        name : str
            The name of the event, eg "on_precommand"
        species : subclass of AbstractEvent
            The type to turn the event in to.
        """
        if isinstance(species, str):
            species = globals()[species]

        if not issubclass(species, AbstractEvent):
            raise ValueError("Invalid event class; must be a subclass of AbstractEvent")

        oldevent = getattr(self, name)
        newevent = self._mkevent(name, species, type(oldevent).__doc__)
        setattr(self, name, newevent)

        for handler in oldevent:
            newevent.add(handler)

    def exists(self, name):
        """Checks if an event with a given name exist. If it does not exist, it
        will not be created. That is what makes this different than
        ``hasattr(events, name)``, which will create the event.
        """
        return name in self.__dict__

    def __getattr__(self, name):
        """Get an event, if it doesn't already exist."""
        if name.startswith("_"):
            raise AttributeError
        # This is only called if the attribute doesn't exist, so create the Event...
        e = self._mkevent(name)
        # ... and save it.
        setattr(self, name, e)
        # Now it exists, and we won't be called again.
        return e


# Not lazy because:
# 1. Initialization of EventManager can't be much cheaper
# 2. It's expected to be used at load time, negating any benefits of using lazy object
events = EventManager()
