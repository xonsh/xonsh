import threading


class HistoryGC(threading.Thread):
    pass


class HistoryBase:
    def __init__(self, gc=True, **kwargs):
        self.gc = HistoryGC() if gc else None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

    def __iter__(self):
        for cmd, ts, index in []:
            yield (cmd, ts, index)

    def append(self, cmd):
        pass

    def flush(self, at_exit=False):
        pass

    def items(self):
        return []

    def show_info(self):
        pass
