"""Implements the xonsh history object"""
import os
import uuid
import time
import builtins
from glob import iglob
from collections import deque, Sequence
from threading import Thread, Condition

from xonsh import lazyjson


class HistoryGC(Thread):

    def __init__(self, wait_for_shell=True, *args, **kwargs):
        """Thread responsible for garbage collecting old history. May wait for 
        shell (and thus xonshrc to have been loaded) to start work.
        """
        super(HistoryGC, self).__init__(*args, **kwargs)
        self.daemon = True
        self.wait_for_shell = wait_for_shell
        self.start()

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        hsize, units = builtins.__xonsh_env__.get('XONSH_HISTORY_SIZE', (8128, 'files'))
        files = self.unlocked_files()
        # flag files for removal
        if units == 'files':
            rmfiles = files[:-hsize] if len(files) > hsize else []
        elif units == 's':
            now = time.time()
            rmfiles = []
            for ts, f in files:
                if (now - ts) < hsize:
                    break
                rmfiles.append((None, f))
        elif units == 'b':
            n = 0
            nbytes = 0
            for f in files[::-1]:
                fsize = os.stat(f).st_size
                if nbytes + fsize > hsize:
                    break
                nbytes += fsize
                n += 1
            rmfiles = f[-n:]    
        else:
            raise ValueError('Units of {0!r} not understood'.format(unit))
        # finally, clean up files
        for _, f in rmfiles:
            try:
                os.remove(f)
            except OSError:
                pass

    def unlocked_files(self):
        """Finds the history files and returns the ones that are unlocked, this is 
        sorted by the last closed time. Returns a list of (timestamp, file) tuples.
        """
        xdd = os.path.abspath(builtins.__xonsh_env__['XONSH_DATA_DIR'])
        fs = [f for f in iglob(os.path.join(xdd, 'xonsh-*.json'))]
        files = []
        for f in fs:
            try:
                lj = lazyjson.LazyJSON(f, reopen=False)
                if lj['locked']:
                    continue
                files.append((lj['ts'][1], f))
                lj.close()
            except (IOError, OSError):
                continue
        files.sort()
        return files


class HistoryFlusher(Thread):

    def __init__(self, filename, buffer, queue, cond, at_exit=False, *args, **kwargs):
        """Thread for flushing history."""
        super(HistoryFlusher, self).__init__(*args, **kwargs)
        self.filename = filename
        self.buffer = buffer
        self.queue = queue
        queue.append(self)
        self.cond = cond
        self.at_exit = at_exit
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
        with open(self.filename, 'r', newline='\n') as f:
            hist = lazyjson.LazyJSON(f).load()
        hist['cmds'].extend(self.buffer)
        if self.at_exit:
            hist['ts'][1] = time.time()  # apply end time
            hist['locked'] = False
        with open(self.filename, 'w', newline='\n') as f:
            lazyjson.dump(hist, f, sort_keys=True)


class CommandField(Sequence):

    def __init__(self, field, hist, default=None):
        """Represents a field in the 'cmds' portion of history. Will query the buffer
        for the relevant data, if possible. Otherwise it will lazily acquire data from 
        the file.

        Parameters
        ----------
        field : str
            The name of the field to query.
        hist : History object
            The history object to query.
        default : optional
            The default value to return if key is not present.
        """
        self.field = field
        self.hist = hist
        self.default = default

    def __len__(self):
        return len(self.hist)

    def __getitem__(self, key):
        size = len(self)
        if isinstance(key, slice):
            return [self[i] for i in range(*key.indices(size))]
        elif not isinstance(key, int):
            raise IndexError('CommandField may only be indexed by int or slice.')
        # now we know we have an int
        key = size + key if key < 0 else key  # ensure key is non-negative
        bufsize = len(self.hist.buffer)
        if size - bufsize <= key:  # key is in buffer
            return self.hist.buffer[key + bufsize - size].get(self.field, self.default)
        # now we know we have to go into the file
        queue = self.hist.queue
        queue.append(self)
        with self.hist.cond as cond:
            cond.wait_for(self.i_am_at_the_front)
            with open(self.hist.filename, 'r', newline='\n') as f:
                lj = lazyjson.LazyJSON(f, reopen=False)
                rtn = lj['cmds'][key].get(self.field, self.default)
                if isinstance(rtn, lazyjson.Node):
                    rtn = rtn.load()
            queue.popleft()
        return rtn

    def i_am_at_the_front(self):
        return self is self.hist.queue[0]


class History(object):

    def __init__(self, filename=None, sessionid=None, buffersize=100, gc=True, **meta):
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
        gc : bool, optional
            Run garbage collector flag.
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
        self._len = 0
        self.last_cmd_out = None
        self.last_cmd_rtn = None
        meta['cmds'] = []
        meta['sessionid'] = str(sid)
        with open(self.filename, 'w', newline='\n') as f:
            lazyjson.dump(meta, f, sort_keys=True)
        self.gc = HistoryGC() if gc else None
        # command fields that are known
        self.tss = CommandField('ts', self)
        self.inps = CommandField('inp', self)
        self.outs = CommandField('out', self)
        self.rtns = CommandField('rtn', self)

    def __len__(self):
        return self._len

    def append(self, cmd):
        """Appends command to history. Will periodically flush the history to file.

        Parameters
        ----------
        cmd : dict 
            Command dictionary that should be added to the ordered history.

        Returns
        -------
        hf : HistoryFlusher or None
            The thread that was spawned to flush history
        """
        self.buffer.append(cmd)
        self._len += 1  # must come before flushing
        if len(self.buffer) >= self.buffersize:
            hf = self.flush()
        else:
            hf = None
        return hf

    def flush(self, at_exit=False):
        """Flushes the current command buffer to disk.

        Parameters
        ----------
        at_exit : bool, optional
            Whether the HistoryFlusher should act as a thread in the background, 
            or execute immeadiately and block.

        Returns
        -------
        hf : HistoryFlusher or None
            The thread that was spawned to flush history
        """
        if len(self.buffer) == 0:
            return
        hf = HistoryFlusher(self.filename, tuple(self.buffer), self._queue, self._cond, 
                            at_exit=at_exit)
        self.buffer.clear()
        return hf
