"""Context management tools for xonsh."""
import builtins

from xonsh.tools import XonshBlockError

class BlockOfLines(object):
    """This is a context manager for obtaining a block of lines without actually
    executing this block. The lines are accessible as the 'lines' attribute.
    """
    __xonsh_block__ = True

    def __init__(self, lines=None):
        """
        Attributes
        ----------
        lines : str or None
            Block lines as a string, if available.
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
        self.locs = exc_value.locs
        return True