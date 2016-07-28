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

    Note that ordering is never guarenteed.
    """
    def __init__(self, doc=None):
        self.__doc__ = doc

    def handler(self, callable):
        """
        Registers a handler. It's suggested to use this as a decorator.
        """
        self.add(callable)
        return callable

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
            newargs = yield handler(*pargs, **kwargs)
            if newargs is not None:
                pargs = newargs

    def __call__(self, *pargs, **kwargs):
        """
        The simplest use case: Calls each handler in turn with the provided
        arguments and ignore the return values.
        """
        for _ in self.calleach(*pargs, **kwargs):
            pass

    def untilTrue(self, *pargs, **kwargs):
        """
        Calls each handler until one returns something truthy.

        Returns that truthy value.
        """
        for rv in self.calleach(*pargs, **kwargs):
            if rv: 
                return rv

    def untilFalse(self, *pargs, **kwargs):
        """
        Calls each handler until one returns something falsey.
        """
        for rv in self.calleach(*pargs, **kwargs):
            if not rv:
                return

    def loopback(self, *pargs, **kwargs):
        """
        Calls each handler in turn. If it returns a value, the arguments are modified.

        The final result is returned.

        NOTE: Each handler must return the same number of values it was
        passed, or nothing at all.
        """
        calls = self.calleach(*pargs, **kwargs)
        newvals = next(calls)
        while True:
            if newvals is not None:
                if len(pargs) == 1:
                    pargs = newvals,
                else:
                    pargs = newvals
            try:
                newvals = calls.send(pargs)
            except StopIteration:
                break

        if newvals is not None:
            return newvals
        else:
            return pargs

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
