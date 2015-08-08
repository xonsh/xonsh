"""Implements the xonsh history object"""
import os
import uuid
import builtins
from threading import Thread, Condition
from collections import deque

from xonsh import lazyjson


class HistoryFlusher(Thread):

    def __init__(self, filename, buffer, queue, cond, at_exit=False, *args, **kwargs):
        """Thread for flushing history."""
        super(HistoryFlusher, self).__init__(*args, **kwargs)
        self.filename = filename
        self.buffer = buffer
        self.queue = queue
        queue.append(self)
        self.cond = cond
        if at_exit:
            self.dump()
        else:
            self.start()

    def run(self):
        with self.cond:
            self.cond.wait_for(self.i_am_at_the_front)
            self.dump()
            self.queue.popleft()

    def i_am_at_the_front(self):
        return self is self.queue[0]

    def dump(self):
        with open(self.filename, 'r') as f:
            hist = lazyjson.LazyJSON(f).load()
        hist['cmds'].extend(self.buffer)
        with open(self.filename, 'w') as f:
            lazyjson.dump(hist, f, sort_keys=True)


class History(object):

    def __init__(self, filename=None, sessionid=None, buffersize=2, **meta):
        """Represents a xonsh session's history as an in-memory buffer that is
        periodically flushed to disk.

        Parameters
        ----------
        filename : str, optional
            Location of history file, defaults to 
            ``$XONSH_DATA_DIR/xonsh-{sessionid}.json``.
        sessionid : int, uuid, str, optional
            Current session identifier, will generate a new sessionid if not set.
        buffersize : int, optional
            Maximum buffersize in memory.
        meta : optional
            Top-level metadata to store along with the history. The kwargs 'cmds' and 
            'sessionid' are not allowed and will be overwritten.
        """
        self.sessionid = sid = uuid.uuid4() if sessionid is None else sessionid
        if filename is None: 
            self.filename = os.path.join(builtins.__xonsh_env__['XONSH_DATA_DIR'], 
                                         'xonsh-{0}.json'.format(sid))
        else: 
            self.filename = filename
        self.buffer = []
        self.buffersize = buffersize
        self._queue = deque()
        self._cond = Condition()
        meta['cmds'] = []
        meta['sessionid'] = str(sid)
        with open(self.filename, 'w') as f:
            lazyjson.dump(meta, f, sort_keys=True)

    def append(self, cmd):
        """Appends command to history. Will periodically flush the history to file.

        Parameters
        ----------
        cmd : dict 
            Command dictionary that should be added to the ordered history.
        """
        self.buffer.append(cmd)
        if len(self.buffer) >= self.buffersize:
            self.flush()

    def flush(self, at_exit=False):
        """Flushes the current command buffer to disk."""
        if len(self.buffer) == 0:
            return
        HistoryFlusher(self.filename, tuple(self.buffer), self._queue, self._cond, 
                       at_exit=at_exit)
        self.buffer.clear()

