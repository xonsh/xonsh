"""Context management tools for xonsh."""
import builtins

class BlockOfLines(object):
    """This is a context manager for obtaining a block of lines without actually
    executing this block. The lines are accessible as the 'lines' attribute.
    """

    def __init__(self, lines=None):
        """
        Parameters
        ----------
        lines : MutableSequence or None, optional
            Lines to begin the block with.
        """
        self.lines = [] if lines is None else lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass
