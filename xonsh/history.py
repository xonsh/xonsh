"""Implements the xonsh history object"""
import os
import time
import uuid
import builtins
from threading import Thread, Condition
from collections import deque

from xonsh import lazyjson


class HistoryFlusher(Thread):

    def __init__(self, filename, buffer, queue, cond, *args, **kwargs):
        """Thread for flushing history."""
        super(HistoryFlusher, self).__init__(*args, **kwargs)
        self.filename = filename
        self.buffer = buffer
        self.queue = queue
        queue.append(self)
        self.cond = cond
        self.running = True
        self.start()

    def run(self):
        with self.cond:
            self.cond.wait_for(self.i_am_at_the_front)
            with open(self.filename, 'w') as f:
                lazyjson.dump(self.buffer, f, sort_keys=True)
            queue.popleft()
        self.running = False

    def i_am_at_the_front(self):
        return self is self.queue[0]


class History(object):

    def __init__(self, filename=None, sessionid=None, buffersize=100):
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
        """
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        if filename is None: 
            self.filename = os.path.join(builtins.__xonsh_env__['XONSH_DATA_DIR'], 
                                         'xonsh-{0}.json'.format(self.sessionid))
        else: 
            self.filename = filename
        self.buffer = []
        self.buffersize = buffersize
        self._queue = deque()
        self._cond = Condition()

    def __del__(self):
        if len(self.buffer) == 0:
            return
        flusher = HistoryFlusher(self.filename, tuple(self.buffer), self._queue, self._cond)
        with self._cond:
            self._cond.wait_for(lambda: not flusher.running)

    def open_history(self):
        """Loads previous history from ~/.xonsh_history.json or
        location specified in .xonshrc if it exists.
        """
        #if os.path.exists(self.hf):
        #    self.ordered_history = lazyjson.LazyJSON(self.hf).load()
        #else:
        #    sys.stdout.write("No history\n")


    def close_history(self):
        pass
        #with open(self.hf, 'w+') as fp:
        #    lazyjson.dump(self.ordered_history, fp) 


    def append(self, cmd):
        """Adds command with current timestamp to ordered history. Will periodically
        flush the history to file.

        Parameters
        ----------
        cmd : dict 
            Command dictionary that should be added to the ordered history.
        """
        cmd['timestamp'] = time.time()
        self.buffer.append(cmd)
        if len(self.buffer) >= self.buffersize:
            HistoryFlusher(self.filename, tuple(self.buffer), self._queue, self._cond)
            self.buffer.clear()
