"""Tools for diff'ing two xonsh history files in a meaningful fashion."""
from difflib import SequenceMatcher

from xonsh import lazyjson


class HistoryDiffer(object):
    """This class helps diff two xonsh history files."""

    def __init__(self, afile, bfile, reopen=False):
        """
        Parameters
        ----------
        afile : file handle or str
            The first file to diff
        bfile : file handle or str
            The second file to diff
        reopen : bool, optional
            Whether or not to reopen the file handles each time. The default here is
            opposite from the LazyJSON default because we know that we will be doing
            a lot of reading so it is best to keep the handles open.
        """
        self.a = lazyjson.LazyJSON(afile, reopen=reopen)
        self.b = lazyjson.LazyJSON(bfile, reopen=reopen)

    def __del__(self):
        self.a.close()
        self.b.close()

    def __str__(self):
        return self.format()

    def format(self):
        """Formats the difference between the two history files."""
        
        return ''
