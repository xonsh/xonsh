"""
Events for xonsh.

In all likelihood, you want builtins.__xonsh_events__

The best way to "declare" an event is something like::

    __xonsh_events__.on_spam.__doc__ = "Comes with eggs"
"""


class Event(set):
    """
    A given event that handlers can register against.

    Acts as a ``set`` for registered handlers.

    Note that ordering is never guaranteed.
    """
    def __init__(self, doc=None):
        self.__doc__ = doc

    def handler(self, func):
        """
        Registers a handler. It's suggested to use this as a decorator.

        A decorator method is added to the handler, validator(). If a validator
        function is added, it can filter if the handler will be considered. The
        validator takes the same arguments as the handler. If it returns False,
        the handler will not called or considered, as if it was not registered
        at all.
        """
        #  Using Pythons "private" munging to minimize hypothetical collisions
        func.__validator = None
        self.add(func)

        def validator(vfunc):
            """
            Adds a validator function to a handler to limit when it is considered.
            """
            func.__validator = vfunc
        func.validator = validator

        return func

    def calleach(self, *pargs, **kwargs):
        """
        The core handler caller that all others build on.

        This works as a generator. Each handler is called in turn and its
        results are yielded.

        If the generator is interupted, no further handlers are called.

        The caller may send() new positional arguments (eg, to implement
        modifying semantics). Keyword arguments cannot be modified this way.
        """
        for handler in self:
            if handler.__validator is not None and not handler.__validator(*pargs, **kwargs):
                continue
            yield handler(*pargs, **kwargs)

    def __call__(self, *pargs, **kwargs):
        """
        The simplest use case: Calls each handler in turn with the provided
        arguments and ignore the return values.
        """
        for _ in self.calleach(*pargs, **kwargs):
            pass

    def until_true(self, *pargs, **kwargs):
        """
        Calls each handler until one returns something truthy.

        Returns that truthy value.
        """
        for rv in self.calleach(*pargs, **kwargs):
            if rv:
                return rv

    def until_false(self, *pargs, **kwargs):
        """
        Calls each handler until one returns something falsey.
        """
        for rv in self.calleach(*pargs, **kwargs):
            if not rv:
                return rv

class Events:
    """
    Container for all events in a system.

    Meant to be a singleton, but doesn't enforce that itself.

    Each event is just an attribute. They're created dynamically on first use.
    """

    def __getattr__(self, name):
        e = Event()
        setattr(self, name, e)
        return e
