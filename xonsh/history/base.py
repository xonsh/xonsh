import uuid
import xonsh.tools as xt


class HistoryBase:
    def __init__(self, sessionid=None, **kwargs):
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        self.gc = None
        self.buffer = None
        self.filename = None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

    def __len__(self):
        return len(list(self.session_items()))

    def __getitem__(self, item):
        """Retrieve history parts based on filtering rules,
        see ``History`` docs for more info. Accepts one of
        int, string, slice or tuple of length two.
        """
        if isinstance(item, tuple):
            cmd_pat, arg_pat = item
        else:
            cmd_pat, arg_pat = item, None
        cmds = [c['inp'] for c in self.session_items()]
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
        pass

    def flush(self, **kwargs):
        pass

    def items(self):
        """Display all history items."""
        raise NotImplementedError

    def session_items(self):
        """Display history items of current session."""
        raise NotImplementedError

    def info(self, ns, stdout=None, stderr=None):
        """A collection of information about the shell history.

        Returns
        -------
        dict or collections.OrderedDict
            Contains history information as str key pairs.
        """
        raise NotImplementedError

    def run_gc(self, size=None, blocking=True):
        """Run a garbage collect action.

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
