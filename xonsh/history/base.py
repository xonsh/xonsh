# -*- coding: utf-8 -*-
"""Base class of Xonsh History backends."""
import types
import uuid


class HistoryEntry(types.SimpleNamespace):
    """Represent a command in history.

    Attributes
    ----------
    cmd: str
        The command as typed by the user, including newlines
    out: str
        The output of the command, if xonsh is configured to save it
    rtn: int
        The return of the command (ie, 0 on success)
    ts: two-tuple of floats
        The timestamps of when the command started and finished, including
        fractions.

    """


class History:
    """Xonsh history backend base class.

    History objects should be created via a subclass of History.

    Indexing
    --------
    History acts like a sequence that can be indexed to return
    ``HistoryEntry`` objects.

    Note that the most recent command is the last item in history.

    Attributes
    ----------
    rtns : sequence of ints
        The return of the command (ie, 0 on success)
    inps : sequence of strings
        The command as typed by the user, including newlines
    tss : sequence of two-tuples of floats
        The timestamps of when the command started and finished, including
        fractions
    outs : sequence of strings
        The output of the command, if xonsh is configured to save it
    gc : A garbage collector or None
        The garbage collector

    In all of these sequences, index 0 is the oldest and -1 (the last item)
    is the newest.
    """
    def __init__(self, sessionid=None, **kwargs):
        """Represents a xonsh session's history.

        Parameters
        ----------
        sessionid : int, uuid, str, optional
            Current session identifier, will generate a new sessionid if not
            set.
        """
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        self.gc = None
        self.buffer = None
        self.filename = None
        self.inps = None
        self.rtns = None
        self.tss = None
        self.outs = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

    def __len__(self):
        """Return the number of items in current session."""
        return len(list(self.items()))

    def __getitem__(self, item):
        """Retrieve history entries, see ``History`` docs for more info."""
        if isinstance(item, int):
            if item >= len(self):
                raise IndexError('history index out of range')
            return HistoryEntry(cmd=self.inps[item], out=self.outs[item],
                                rtn=self.rtns[item], ts=self.tss[item])
        elif isinstance(item, slice):
            cmds = self.inps[item]
            outs = self.outs[item]
            rtns = self.rtns[item]
            tss = self.tss[item]
            return [HistoryEntry(cmd=c, out=o, rtn=r, ts=t)
                    for c, o, r, t in zip(cmds, outs, rtns, tss)]
        else:
            raise TypeError('history indices must be integers '
                            'or slices, not {}'.format(type(item)))

    def __setitem__(self, *args):
        raise PermissionError('You cannot change history! '
                              'you can create new though.')

    def append(self, cmd):
        """Append a command item into history.

        Parameters
        ----------
        cmd: dict
            This dict contains information about the command that is to be
            added to the history list. It should contain the keys ``inp``,
            ``rtn`` and ``ts``. These key names mirror the same names defined
            as instance variables in the ``HistoryEntry`` class.
        """
        pass

    def flush(self, **kwargs):
        """Flush the history items to disk from a buffer."""
        pass

    def items(self):
        """Get history items of current session."""
        raise NotImplementedError

    def all_items(self):
        """Get all history items."""
        raise NotImplementedError

    def info(self):
        """A collection of information about the shell history.

        Returns
        -------
        dict or collections.OrderedDict
            Contains history information as str key pairs.
        """
        raise NotImplementedError

    def run_gc(self, size=None, blocking=True):
        """Run the garbage collector.

        Parameters
        ----------
        size: None or tuple of a int and a string
            Determines the size and units of what would be allowed to remain.
        blocking: bool
            If set blocking, then wait until gc action finished.
        """
        pass
