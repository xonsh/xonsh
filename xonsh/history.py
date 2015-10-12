"""Implements the xonsh history object"""
import os
import uuid
import time
import builtins
from glob import iglob
from collections import deque, Sequence, OrderedDict
from threading import Thread, Condition

from xonsh import lazyjson
from xonsh.tools import ensure_int_or_slice, to_history_tuple
from xonsh import diff_history


class HistoryGC(Thread):

    def __init__(self, wait_for_shell=True, size=None, *args, **kwargs):
        """Thread responsible for garbage collecting old history. May wait for 
        shell (and thus xonshrc to have been loaded) to start work.
        """
        super(HistoryGC, self).__init__(*args, **kwargs)
        self.daemon = True
        self.size = size
        self.wait_for_shell = wait_for_shell
        self.start()

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        env = builtins.__xonsh_env__
        if self.size is None:
            hsize, units = env.get('XONSH_HISTORY_SIZE')
        else:
            hsize, units = to_history_tuple(self.size)
        files = self.unlocked_files()
        # flag files for removal
        if units == 'commands':
            n = 0
            ncmds = 0
            rmfiles = []
            for ts, fcmds, f in files[::-1]:
                if fcmds == 0:
                    # we need to make sure that 'empty' history files don't hang around
                    fmfiles.append((ts, fcmds, f))
                if ncmds + fcmds > hsize:
                    break
                ncmds += fcmds
                n += 1
            rmfiles += files[:-n]
        elif units == 'files':
            rmfiles = files[:-hsize] if len(files) > hsize else []
        elif units == 's':
            now = time.time()
            rmfiles = []
            for ts, _, f in files:
                if (now - ts) < hsize:
                    break
                rmfiles.append((None, None, f))
        elif units == 'b':
            n = 0
            nbytes = 0
            for _, _, f in files[::-1]:
                fsize = os.stat(f).st_size
                if nbytes + fsize > hsize:
                    break
                nbytes += fsize
                n += 1
            rmfiles = files[:-n]
        else:
            raise ValueError('Units of {0!r} not understood'.format(unit))
        # finally, clean up files
        for _, _, f in rmfiles:
            try:
                os.remove(f)
            except OSError:
                pass

    def unlocked_files(self):
        """Finds the history files and returns the ones that are unlocked, this is 
        sorted by the last closed time. Returns a list of (timestamp, file) tuples.
        """
        xdd = os.path.abspath(builtins.__xonsh_env__.get('XONSH_DATA_DIR'))
        fs = [f for f in iglob(os.path.join(xdd, 'xonsh-*.json'))]
        files = []
        for f in fs:
            try:
                lj = lazyjson.LazyJSON(f, reopen=False)
                if lj['locked']:
                    continue
                # info: closing timestamp, number of commands, filename
                files.append((lj['ts'][1], len(lj.sizes['cmds']) - 1, f))
                lj.close()
            except (IOError, OSError, ValueError):
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
        queue = self.hist._queue
        queue.append(self)
        with self.hist._cond:
            self.hist._cond.wait_for(self.i_am_at_the_front)
            with open(self.hist.filename, 'r', newline='\n') as f:
                lj = lazyjson.LazyJSON(f, reopen=False)
                rtn = lj['cmds'][key].get(self.field, self.default)
                if isinstance(rtn, lazyjson.Node):
                    rtn = rtn.load()
            queue.popleft()
        return rtn

    def i_am_at_the_front(self):
        """Tests if the command field is at the front of the queue."""
        return self is self.hist._queue[0]


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
            self.filename = os.path.join(builtins.__xonsh_env__.get('XONSH_DATA_DIR'), 
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

#
# Interface to History
#

_HIST_PARSER = None

def _create_parser():
    global _HIST_PARSER
    if _HIST_PARSER is not None:
        return _HIST_PARSER
    from argparse import ArgumentParser
    p = ArgumentParser(prog='history', 
                       description='Tools for dealing with history')
    subp = p.add_subparsers(title='action', dest='action')
    # show action
    show = subp.add_parser('show', help='displays current history, default action')
    show.add_argument('-r', dest='reverse', default=False, action='store_true',
                      help='reverses the direction')
    show.add_argument('n', nargs='?', default=None, 
                      help='displays n current history entries, n may be an int or use '
                           'Python slice notation')
    # id
    idp = subp.add_parser('id', help='displays the current session id')
    # file
    fp = subp.add_parser('file', help='displays the current history filename')
    # info
    info = subp.add_parser('info', help='displays information about the current history')
    info.add_argument('--json', dest='json', default=False, action='store_true',
                      help='print in JSON format')
    # diff
    diff = subp.add_parser('diff', help='diffs two xonsh history files')
    diff_history._create_parser(p=diff)
    # replay, dynamically
    from xonsh import replay
    rp = subp.add_parser('replay', help='replays a xonsh history file')
    replay._create_parser(p=rp)
    _MAIN_ACTIONS['replay'] = replay._main_action
    # gc
    gcp = subp.add_parser('gc', help='launches a new history garbage collector')
    gcp.add_argument('--size', nargs=2, dest='size', default=None,
                     help='next two arguments represent the history size and units, '
                          'eg "--size 8128 commands"')
    bgcp = gcp.add_mutually_exclusive_group()
    bgcp.add_argument('--blocking', dest='blocking', default=True, action='store_true',
                      help='ensures that the gc blocks the main thread, default True')
    bgcp.add_argument('--non-blocking', dest='blocking', action='store_false', 
                      help='makes the gc non-blocking, and thus return sooner')
    # set and return
    _HIST_PARSER = p
    return p


def _show(ns, hist):
    idx = ensure_int_or_slice(ns.n)
    if len(hist) == 0:
        return
    inps = hist.inps[idx]
    if isinstance(idx, int):
        inps = [inps]
        indices = [idx if idx >= 0 else len(hist) + idx]
    else: 
        indices = list(range(*idx.indices(len(hist))))
    ndigits = len(str(indices[-1]))
    indent = ' '*(ndigits + 3)
    if ns.reverse:
        indices = reversed(indices)
        inps = reversed(inps)
    for i, inp in zip(indices, inps):
        lines = inp.splitlines()
        lines[0] = ' {0:>{1}}  {2}'.format(i, ndigits, lines[0])
        lines[1:] = [indent + x for x in lines[1:]]
        print('\n'.join(lines))


def _info(ns, hist):
    data = OrderedDict()
    data['sessionid'] = str(hist.sessionid)
    data['filename'] = hist.filename
    data['length'] = len(hist)
    data['buffersize'] = hist.buffersize
    data['bufferlength'] = len(hist.buffer)
    if ns.json:
        import json
        s = json.dumps(data)
        print(s)
    else:
        lines = ['{0}: {1}'.format(k, v) for k, v in data.items()]
        print('\n'.join(lines))


def _gc(ns, hist):
    hist.gc = gc = HistoryGC(wait_for_shell=False, size=ns.size)
    if ns.blocking:
        while gc.is_alive():
            continue
    

_MAIN_ACTIONS = {
    'show': _show,
    'id': lambda ns, hist: print(hist.sessionid),
    'file': lambda ns, hist: print(hist.filename),
    'info': _info,
    'diff': diff_history._main_action,
    'gc': _gc,
    }

def main(args=None, stdin=None):
    """This acts as a main funtion for history command line interfaces."""
    hist = builtins.__xonsh_history__
    parser = _create_parser()
    ns = parser.parse_args(args)
    if ns.action is None:  # apply default action
        ns = parser.parse_args(['show'] + args)
    _MAIN_ACTIONS[ns.action](ns, hist)
