"""Context management tools for xonsh."""
import sys
import textwrap
import builtins
from collections.abc import Mapping


class Block(object):
    """This is a context manager for obtaining a block of lines without actually
    executing the block. The lines are accessible as the 'lines' attribute.
    This must be used as a macro.
    """

    __xonsh_block__ = str

    def __init__(self):
        """
        Attributes
        ----------
        lines : list of str or None
            Block lines as if split by str.splitlines(), if available.
        glbs : Mapping or None
            Global execution context, ie globals().
        locs : Mapping or None
            Local execution context, ie locals().
        """
        self.lines = self.glbs = self.locs = None

    def __enter__(self):
        if not hasattr(self, "macro_block"):
            raise XonshError(self.__class__.__name__ + " must be entered as a macro!")
        self.lines = self.macro_block.splitlines()
        self.glbs = self.macro_globals
        if self.macro_locals is not self.macro_globals:
            # leave locals as None when it is the same as globals
            self.locs = self.macro_locals
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class Functor(Block):
    """This is a context manager that turns the block into a callable
    object, bound to the execution context it was created in.
    """

    def __init__(self, args=(), kwargs=None, rtn=""):
        """
        Parameters
        ----------
        args : Sequence of str, optional
            A tuple of argument names for the functor.
        kwargs : Mapping of str to values or list of item tuples, optional
            Keyword argument names and values, if available.
        rtn : str, optional
            Name of object to return, if available.

        Attributes
        ----------
        func : function
            The underlying function object. This defaults to none and is set
            after the the block is exited.
        """
        super().__init__()
        self.func = None
        self.args = args
        if kwargs is None:
            self.kwargs = []
        elif isinstance(kwargs, Mapping):
            self.kwargs = sorted(kwargs.items())
        else:
            self.kwargs = kwargs
        self.rtn = rtn

    def __enter__(self):
        super().__enter__()
        body = textwrap.indent(self.macro_block, "    ")
        uid = hash(body) + sys.maxsize  # should always be a positive int
        name = "__xonsh_functor_{uid}__".format(uid=uid)
        # construct signature string
        sig = rtn = ""
        sig = ", ".join(self.args)
        kwstr = ", ".join([k + "=None" for k, _ in self.kwargs])
        if len(kwstr) > 0:
            sig = kwstr if len(sig) == 0 else sig + ", " + kwstr
        # construct return string
        rtn = str(self.rtn)
        if len(rtn) > 0:
            rtn = "    return " + rtn + "\n"
        # construct function string
        fstr = "def {name}({sig}):\n{body}\n{rtn}"
        fstr = fstr.format(name=name, sig=sig, body=body, rtn=rtn)
        glbs = self.glbs
        locs = self.locs
        execer = builtins.__xonsh__.execer
        execer.exec(fstr, glbs=glbs, locs=locs)
        if locs is not None and name in locs:
            func = locs[name]
        elif name in glbs:
            func = glbs[name]
        else:
            raise ValueError("Functor block could not be found in context.")
        if len(self.kwargs) > 0:
            func.__defaults__ = tuple(v for _, v in self.kwargs)
        self.func = func
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __call__(self, *args, **kwargs):
        """Dispatches to func."""
        if self.func is None:
            msg = "{} block with 'None' func not callable"
            raise AttributeError(msg.formst(self.__class__.__name__))
        return self.func(*args, **kwargs)
