import threading
import uuid

import xonsh.tools as xt


class HistoryGC(threading.Thread):
    pass


class HistoryBase:
    def __init__(self, sessionid=None, gc=True, **kwargs):
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        self.gc = HistoryGC() if gc else None
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

    def on_info(self, ns, stdout=None, stderr=None):
        """Display information about the shell history."""
        pass

    def on_id(self, ns, stdout=None, stderr=None):
        """Display history sessionid."""
        if not self.sessionid:
            return
        print(str(self.sessionid), file=stdout)

    def on_file(self, ns, stdout=None, stderr=None):
        """Display history file name if it exists."""
        if not self.filename:
            return
        print(str(self.filename), file=stdout)

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
