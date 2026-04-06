"""Lazy and self destructive containers for speeding up module import."""

# Copyright 2015-2016, the xonsh developers. All rights reserved.
import collections.abc as cabc
import threading
import typing as tp

__version__ = "0.1.3"


class LazyObject:
    def __init__(self, load, ctx, name):
        """Lazily loads an object via the load function the first time an
        attribute is accessed. Once loaded it will replace itself in the
        provided context (typically the globals of the call site) with the
        given name.

        For example, you can prevent the compilation of a regular expression
        until it is actually used::

            DOT = LazyObject((lambda: re.compile('.')), globals(), 'DOT')

        Parameters
        ----------
        load : function with no arguments
            A loader function that performs the actual object construction.
        ctx : Mapping
            Context to replace the LazyObject instance in
            with the object returned by load().
        name : str
            Name in the context to give the loaded object. This *should*
            be the name on the LHS of the assignment.
        """
        self._lasdo = {"loaded": False, "load": load, "ctx": ctx, "name": name}
        self._lasdo_lock = threading.Lock()

    def _lazy_obj(self):
        d = self._lasdo
        if d["loaded"]:
            return d["obj"]
        with self._lasdo_lock:
            if d["loaded"]:
                return d["obj"]
            obj = d["load"]()
            d["ctx"][d["name"]] = d["obj"] = obj
            d["loaded"] = True
        return obj

    def __getattribute__(self, name):
        if name in ("_lasdo", "_lasdo_lock", "_lazy_obj"):
            return super().__getattribute__(name)
        obj = self._lazy_obj()
        return getattr(obj, name)

    def __bool__(self):
        obj = self._lazy_obj()
        return bool(obj)

    def __iter__(self):
        obj = self._lazy_obj()
        yield from obj

    def __getitem__(self, item):
        obj = self._lazy_obj()
        return obj[item]

    def __setitem__(self, key, value):
        obj = self._lazy_obj()
        obj[key] = value

    def __delitem__(self, item):
        obj = self._lazy_obj()
        del obj[item]

    def __call__(self, *args, **kwargs):
        obj = self._lazy_obj()
        return obj(*args, **kwargs)

    def __lt__(self, other):
        obj = self._lazy_obj()
        return obj < other

    def __le__(self, other):
        obj = self._lazy_obj()
        return obj <= other

    def __eq__(self, other):
        obj = self._lazy_obj()
        return obj == other

    def __ne__(self, other):
        obj = self._lazy_obj()
        return obj != other

    def __gt__(self, other):
        obj = self._lazy_obj()
        return obj > other

    def __ge__(self, other):
        obj = self._lazy_obj()
        return obj >= other

    def __hash__(self):
        obj = self._lazy_obj()
        return hash(obj)

    def __or__(self, other):
        obj = self._lazy_obj()
        return obj | other

    def __str__(self):
        return str(self._lazy_obj())

    def __repr__(self):
        return repr(self._lazy_obj())

    def __len__(self):
        return len(self._lazy_obj())


RT = tp.TypeVar("RT")


def lazyobject(f: tp.Callable[..., RT]) -> RT:
    """Decorator for constructing lazy objects from a function."""
    return LazyObject(f, f.__globals__, f.__name__)  # type: ignore


class LazyCallable:
    """Lazy proxy that defers loading until first call or attribute access.

    Unlike LazyObject, this does NOT override __getattribute__, so it survives
    isinstance() checks without triggering the load. The real object is loaded
    on first __call__ or __getattr__.

    Usage::

        def my_alias():
            from xonsh.heavy_module import real_alias
            return real_alias

        my_alias = LazyCallable(my_alias)
    """

    def __init__(self, load):
        self._lazy_load = load
        self._lazy_obj = None

    def _get(self):
        if self._lazy_obj is None:
            self._lazy_obj = self._lazy_load()
        return self._lazy_obj

    def __call__(self, *args, **kwargs):
        return self._get()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._get(), name)


class LazyDict(cabc.MutableMapping):
    def __init__(self, loaders, ctx, name):
        """Dictionary like object that lazily loads its values from an initial
        dict of key-loader function pairs.  Each key is loaded when its value
        is first accessed. Once fully loaded, this object will replace itself
        in the provided context (typically the globals of the call site) with
        the given name.

        For example, you can prevent the compilation of a bunch of regular
        expressions until they are actually used::

            RES = LazyDict({
                    'dot': lambda: re.compile('.'),
                    'all': lambda: re.compile('.*'),
                    'two': lambda: re.compile('..'),
                    }, globals(), 'RES')

        Parameters
        ----------
        loaders : Mapping of keys to functions with no arguments
            A mapping of loader function that performs the actual value
            construction upon access.
        ctx : Mapping
            Context to replace the LazyDict instance in
            with the the fully loaded mapping.
        name : str
            Name in the context to give the loaded mapping. This *should*
            be the name on the LHS of the assignment.
        """
        self._loaders = loaders
        self._ctx = ctx
        self._name = name
        self._d = type(loaders)()  # make sure to return the same type

    def _destruct(self):
        if len(self._loaders) == 0:
            self._ctx[self._name] = self._d

    def __getitem__(self, key):
        d = self._d
        if key in d:
            val = d[key]
        else:
            # pop will raise a key error for us
            loader = self._loaders.pop(key)
            d[key] = val = loader()
            self._destruct()
        return val

    def __setitem__(self, key, value):
        self._d[key] = value
        if key in self._loaders:
            del self._loaders[key]
            self._destruct()

    def __delitem__(self, key):
        if key in self._d:
            del self._d[key]
        else:
            del self._loaders[key]
            self._destruct()

    def __iter__(self):
        yield from (set(self._d.keys()) | set(self._loaders.keys()))

    def __len__(self):
        return len(self._d) + len(self._loaders)


def lazydict(f):
    """Decorator for constructing lazy dicts from a function."""
    return LazyDict(f, f.__globals__, f.__name__)


class LazyBool:
    def __init__(self, load, ctx, name):
        """Boolean like object that lazily computes it boolean value when it is
        first asked. Once loaded, this result will replace itself
        in the provided context (typically the globals of the call site) with
        the given name.

        For example, you can prevent the complex boolean until it is actually
        used::

            ALIVE = LazyDict(lambda: not DEAD, globals(), 'ALIVE')

        Parameters
        ----------
        load : function with no arguments
            A loader function that performs the actual boolean evaluation.
        ctx : Mapping
            Context to replace the LazyBool instance in
            with the the fully loaded mapping.
        name : str
            Name in the context to give the loaded mapping. This *should*
            be the name on the LHS of the assignment.
        """
        self._load = load
        self._ctx = ctx
        self._name = name
        self._result = None

    def __bool__(self):
        if self._result is None:
            res = self._ctx[self._name] = self._result = self._load()
        else:
            res = self._result
        return res


def lazybool(f):
    """Decorator for constructing lazy booleans from a function."""
    return LazyBool(f, f.__globals__, f.__name__)
