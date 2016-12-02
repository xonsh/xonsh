# -*- coding: utf-8 -*-
"""Base class of Xonsh History backends."""
import uuid
import xonsh.tools as xt


class History:
    """Xonsh history backend base class.

    History objects should be created via a subclass of History.

    Indexing
    --------
    History object acts like a sequence that can be indexed in a special
    way that adds extra functionality. Note that the most recent command
    is the last item in history.

    The index acts as a filter with two parts, command and argument,
    separated by comma. Based on the type of each part different
    filtering can be achieved,

        for the command part:

            - an int returns the command in that position.
            - a slice returns a list of commands.
            - a string returns the most recent command containing the string.

        for the argument part:

            - an int returns the argument of the command in that position.
            - a slice returns a part of the command based on the argument
              position.

    The argument part of the filter can be omitted but the command part is
    required. Command arguments are separated by white space.

    If the filtering produces only one result it is returned as a string
    else a list of strings is returned.

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
        """Retrieve history parts based on filtering rules,
        see ``History`` docs for more info. Accepts one of
        int, string, slice or tuple of length two.
        """
        if isinstance(item, tuple):
            cmd_pat, arg_pat = item
        else:
            cmd_pat, arg_pat = item, None
        cmds = [c['inp'] for c in self.items()]
        cmds = self._cmd_filter(cmds, cmd_pat)
        if arg_pat is not None:
            cmds = self._args_filter(cmds, arg_pat)
        cmds = list(cmds)
        if len(cmds) == 1:
            return cmds[0]
        else:
            return cmds

    def __setitem__(self, *args):
        raise PermissionError('You cannot change history! '
                              'you can create new though.')

    def append(self, cmd):
        """Append a command item into history.

        Parameters
        ----------
        cmd: dict
            A dict contains informations of a command. It should contains
            the following keys like ``inp``, ``rtn``, ``ts`` etc.
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
            Detemines the size and units of what would be allowed to remain.
        blocking: bool
            If set blocking, then wait until gc action finished.
        """
        pass

    @staticmethod
    def _cmd_filter(cmds, pat):
        if isinstance(pat, (int, slice)):
            s = xt.ensure_slice(pat)
            yield from xt.get_portions(cmds, s)
        elif xt.is_string(pat):
            for command in reversed(list(cmds)):
                if pat in command:
                    yield command
                    return
        else:
            raise TypeError('Command filter must be string, int or slice')

    @staticmethod
    def _args_filter(cmds, pat):
        args = None
        if isinstance(pat, (int, slice)):
            s = xt.ensure_slice(pat)
            for command in cmds:
                yield ' '.join(command.split()[s])
        else:
            raise TypeError('Argument filter must be int or slice')
        return args
