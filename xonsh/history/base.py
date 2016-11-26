import threading
import uuid


class HistoryGC(threading.Thread):
    pass


class HistoryBase:
    def __init__(self, sessionid=None, gc=True, **kwargs):
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        self.gc = HistoryGC() if gc else None
        self.filename = None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

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
