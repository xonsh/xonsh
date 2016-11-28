# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import os
import time
import uuid
import builtins
import collections
import threading
import collections.abc as cabc

from xonsh.history.base import HistoryBase
import xonsh.tools as xt
import xonsh.lazyjson as xlj


def _xhj_gc_commands_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the command limit."""
    rmfiles = []
    n = 0
    ncmds = 0
    for ts, fcmds, f in files[::-1]:
        if fcmds == 0:
            # we need to make sure that 'empty' history files don't hang around
            rmfiles.append((ts, fcmds, f))
        if ncmds + fcmds > hsize:
            break
        ncmds += fcmds
        n += 1
    rmfiles += files[:-n]
    return rmfiles


def _xhj_gc_files_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the file limit."""
    rmfiles = files[:-hsize] if len(files) > hsize else []
    return rmfiles


def _xhj_gc_seconds_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the age limit."""
    rmfiles = []
    now = time.time()
    for ts, _, f in files:
        if (now - ts) < hsize:
            break
        rmfiles.append((None, None, f))
    return rmfiles


def _xhj_gc_bytes_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the byte limit."""
    rmfiles = []
    n = 0
    nbytes = 0
    for _, _, f in files[::-1]:
        fsize = os.stat(f).st_size
        if nbytes + fsize > hsize:
            break
        nbytes += fsize
        n += 1
    rmfiles = files[:-n]
    return rmfiles


def _xhj_get_history_files(sort=True, reverse=False):
    """Find and return the history files. Optionally sort files by
        modify time.
    """
    data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
    data_dir = xt.expanduser_abs_path(data_dir)
    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
             if f.startswith('xonsh-') and f.endswith('.json')]
    if sort:
        files.sort(key=lambda x: os.path.getmtime(x), reverse=reverse)
    return files


class JsonHistoryGC(threading.Thread):
    """Shell history garbage collection."""

    def __init__(self, wait_for_shell=True, size=None, *args, **kwargs):
        """Thread responsible for garbage collecting old history.

        May wait for shell (and for xonshrc to have been loaded) to start work.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.size = size
        self.wait_for_shell = wait_for_shell
        self.start()
        self.gc_units_to_rmfiles = {'commands': _xhj_gc_commands_to_rmfiles,
                                    'files': _xhj_gc_files_to_rmfiles,
                                    's': _xhj_gc_seconds_to_rmfiles,
                                    'b': _xhj_gc_bytes_to_rmfiles}

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        if self.size is None:
            hsize, units = env.get('XONSH_HISTORY_SIZE')
        else:
            hsize, units = xt.to_history_tuple(self.size)
        files = self.files(only_unlocked=True)
        rmfiles_fn = self.gc_units_to_rmfiles.get(units)
        if rmfiles_fn is None:
            raise ValueError('Units type {0!r} not understood'.format(units))

        for _, _, f in rmfiles_fn(hsize, files):
            try:
                os.remove(f)
            except OSError:
                pass

    def files(self, only_unlocked=False):
        """Find and return the history files. Optionally locked files may be
        excluded.

        This is sorted by the last closed time. Returns a list of
        (timestamp, number of cmds, file name) tuples.
        """
        # pylint: disable=no-member
        env = getattr(builtins, '__xonsh_env__', None)
        if env is None:
            return []

        fs = _xhj_get_history_files(sort=False)
        files = []
        for f in fs:
            try:
                if os.path.getsize(f) == 0:
                    # collect empty files (for gc)
                    files.append((time.time(), 0, f))
                    continue
                lj = xlj.LazyJSON(f, reopen=False)
                if only_unlocked and lj['locked']:
                    continue
                # info: closing timestamp, number of commands, filename
                files.append((lj['ts'][1] or time.time(),
                              len(lj.sizes['cmds']) - 1,
                              f))
                lj.close()
            except (IOError, OSError, ValueError):
                continue
        files.sort()
        return files


class JsonHistoryFlusher(threading.Thread):
    """Flush shell history to disk periodically."""

    def __init__(self, filename, buffer, queue, cond, at_exit=False, *args,
                 **kwargs):
        """Thread for flushing history."""
        super(JsonHistoryFlusher, self).__init__(*args, **kwargs)
        self.filename = filename
        self.buffer = buffer
        self.queue = queue
        queue.append(self)
        self.cond = cond
        self.at_exit = at_exit
        if at_exit:
            self.dump()
            queue.popleft()
        else:
            self.start()

    def run(self):
        with self.cond:
            self.cond.wait_for(self.i_am_at_the_front)
            self.dump()
            self.queue.popleft()

    def i_am_at_the_front(self):
        """Tests if the flusher is at the front of the queue."""
        return self is self.queue[0]

    def dump(self):
        """Write the cached history to external storage."""
        with open(self.filename, 'r', newline='\n') as f:
            hist = xlj.LazyJSON(f).load()
        hist['cmds'].extend(self.buffer)
        if self.at_exit:
            hist['ts'][1] = time.time()  # apply end time
            hist['locked'] = False
        with open(self.filename, 'w', newline='\n') as f:
            xlj.ljdump(hist, f, sort_keys=True)


class JsonCommandField(cabc.Sequence):
    """A field in the 'cmds' portion of history."""

    def __init__(self, field, hist, default=None):
        """Represents a field in the 'cmds' portion of history.

        Will query the buffer for the relevant data, if possible. Otherwise it
        will lazily acquire data from the file.

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
            raise IndexError(
                'JsonCommandField may only be indexed by int or slice.')
        elif size == 0:
            raise IndexError('JsonCommandField is empty.')
        # now we know we have an int
        key = size + key if key < 0 else key  # ensure key is non-negative
        bufsize = len(self.hist.buffer)
        if size - bufsize <= key:  # key is in buffer
            return self.hist.buffer[key + bufsize - size].get(
                self.field, self.default)
        # now we know we have to go into the file
        queue = self.hist._queue
        queue.append(self)
        with self.hist._cond:
            self.hist._cond.wait_for(self.i_am_at_the_front)
            with open(self.hist.filename, 'r', newline='\n') as f:
                lj = xlj.LazyJSON(f, reopen=False)
                rtn = lj['cmds'][key].get(self.field, self.default)
                if isinstance(rtn, xlj.LJNode):
                    rtn = rtn.load()
            queue.popleft()
        return rtn

    def i_am_at_the_front(self):
        """Tests if the command field is at the front of the queue."""
        return self is self.hist._queue[0]


# Interface to History
class JsonHistory(HistoryBase):
    """Xonsh session history.

    Indexing
    --------
    History object acts like a sequence that can be indexed in a special way
    that adds extra functionality. At the moment only history from the
    current session can be retrieved. Note that the most recent command
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
    required.

    Command arguments are separated by white space.

    If the filtering produces only one result it is
    returned as a string else a list of strings is returned.

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

    In all of these sequences, index 0 is the oldest and -1 (the last item) is the newest.
    """

    def __init__(self, filename=None, sessionid=None, buffersize=100, gc=True,
                 **meta):
        """Represents a xonsh session's history as an in-memory buffer that is
        periodically flushed to disk.

        Parameters
        ----------
        filename : str, optional
            Location of history file, defaults to
            ``$XONSH_DATA_DIR/xonsh-{sessionid}.json``.
        sessionid : int, uuid, str, optional
            Current session identifier, will generate a new sessionid if not
            set.
        buffersize : int, optional
            Maximum buffersize in memory.
        meta : optional
            Top-level metadata to store along with the history. The kwargs
            'cmds' and 'sessionid' are not allowed and will be overwritten.
        gc : bool, optional
            Run garbage collector flag.
        """
        self.sessionid = sid = uuid.uuid4() if sessionid is None else sessionid
        if filename is None:
            # pylint: disable=no-member
            data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
            data_dir = os.path.expanduser(data_dir)
            self.filename = os.path.join(
                data_dir, 'xonsh-{0}.json'.format(sid))
        else:
            self.filename = filename
        self.buffer = []
        self.buffersize = buffersize
        self._queue = collections.deque()
        self._cond = threading.Condition()
        self._len = 0
        self.last_cmd_out = None
        self.last_cmd_rtn = None
        meta['cmds'] = []
        meta['sessionid'] = str(sid)
        with open(self.filename, 'w', newline='\n') as f:
            xlj.ljdump(meta, f, sort_keys=True)
        self.gc = JsonHistoryGC() if gc else None
        # command fields that are known
        self.tss = JsonCommandField('ts', self)
        self.inps = JsonCommandField('inp', self)
        self.outs = JsonCommandField('out', self)
        self.rtns = JsonCommandField('rtn', self)

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
        hf : JsonHistoryFlusher or None
            The thread that was spawned to flush history
        """
        opts = builtins.__xonsh_env__.get('HISTCONTROL')
        if ('ignoredups' in opts and len(self) > 0 and
                cmd['inp'] == self.inps[-1]):
            # Skipping dup cmd
            return None
        elif 'ignoreerr' in opts and cmd['rtn'] != 0:
            # Skipping failed cmd
            return None

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
            Whether the JsonHistoryFlusher should act as a thread in the
            background, or execute immeadiately and block.

        Returns
        -------
        hf : JsonHistoryFlusher or None
            The thread that was spawned to flush history
        """
        if len(self.buffer) == 0:
            return
        hf = JsonHistoryFlusher(self.filename, tuple(self.buffer), self._queue,
                                self._cond, at_exit=at_exit)
        self.buffer.clear()
        return hf

    def session_items(self):
        """Display history items of current session."""
        ind = 0
        for item, tss in zip(self.inps, self.tss):
            yield {'inp': item.rstrip(), 'ind': ind, 'ts': tss[0]}
            ind += 1

    def items(self, **kwargs):
        """
        Returns all history as found in XONSH_DATA_DIR.

        return format: (cmd, start_time, index)
        """
        while self.gc.is_alive():
            time.sleep(0.011)  # gc sleeps for 0.01 secs, sleep a beat longer
        ind = 0
        for f in _xhj_get_history_files():
            try:
                json_file = xlj.LazyJSON(f, reopen=False)
            except ValueError:
                # Invalid json file
                continue
            commands = json_file.load()['cmds']
            for c in commands:
                yield {'inp': c['inp'].rstrip(), 'ts': c['ts'][0], 'ind': ind}
                ind += 1

    def info(self):
        data = collections.OrderedDict()
        data['backend'] = 'json'
        data['sessionid'] = str(self.sessionid)
        data['filename'] = self.filename
        data['length'] = len(self)
        data['buffersize'] = self.buffersize
        data['bufferlength'] = len(self.buffer)
        envs = builtins.__xonsh_env__
        data['gc options'] = envs.get('XONSH_HISTORY_SIZE')
        return data

    def run_gc(self, size=None, blocking=True):
        self.gc = JsonHistoryGC(wait_for_shell=False, size=size)
        if blocking:
            while self.gc.is_alive():
                continue
