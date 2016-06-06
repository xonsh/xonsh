"""Context management tools for xonsh."""
import sys
import builtins

from xonsh.tools import XonshBlockError

class Block(object):
    """This is a context manager for obtaining a block of lines without actually
    executing the block. The lines are accessible as the 'lines' attribute.
    """
    __xonsh_block__ = True

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
        self.lines = self.glbs = self.locs = None  # make re-entrant
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not XonshBlockError:
            return  # some other kind of error happened
        self.lines = exc_value.lines
        self.glbs = exc_value.glbs
        if exc_value.locs is not self.glbs:
            # leave locals as None when it is the same as globals
            self.locs = exc_value.locs
        return True


class Functor(Block):
    """This is a context manager that turns the block into a callable
    object, bound to the execution context it was created in.
    """

    def __init__(self):
        """
        Attributes
        ----------
        func : function
            The underlying function object. This defaults to none and is set
            after the the block is exited.
        """
        super().__init__()
        self.func = None

    def __enter__(self):
        super().__enter__()
        self.func = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        rtn = super().__exit__(exc_type, exc_value, traceback)
        if not rtn:
            return rtn
        body = '\n'.join(self.lines)
        uid = hash(body) + sys.maxsize  # should always be a positive int
        name = '__xonsh_functor_{uid}__'.format(uid=uid)
        fstr = 'def {name}():\n{body}\n'
        fstr = fstr.format(name=name, body=body)
        glbs = self.glbs
        locs = self.locs
        #locs = glbs if self.locs is None else self.locs
        execer = builtins.__xonsh_execer__
        execer.exec(fstr, glbs=glbs, locs=locs)
        if locs is not None and name in locs:
            func = locs[name]
        elif name in glbs:
            func = glbs[name]
        else:
            raise exc_value
        self.func = func
        return rtn

    def __call__(self, *args, **kwargs):
        """Dispatches to func."""
        if self.func is None:
            msg = "{} block with 'None' func not callable"
            raise AttributeError(msg.formst(self.__class__.__name__))
        return self.func(*args, **kwargs)
