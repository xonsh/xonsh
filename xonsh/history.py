# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import os
import sys
import glob
import json
import time
import uuid
import argparse
import builtins
import datetime
import functools
import itertools
import threading
import collections
import collections.abc as abc

from xonsh.lazyasd import lazyobject
from xonsh.lazyjson import LazyJSON, ljdump, LJNode
from xonsh.tools import (ensure_slice, to_history_tuple,
                         expanduser_abs_path, ensure_timestamp)
from xonsh.diff_history import _dh_create_parser, _dh_main_action


def _gc_commands_to_rmfiles(hsize, files):
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


def _gc_files_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the file limit."""
    rmfiles = files[:-hsize] if len(files) > hsize else []
    return rmfiles


def _gc_seconds_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the age limit."""
    rmfiles = []
    now = time.time()
    for ts, _, f in files:
        if (now - ts) < hsize:
            break
        rmfiles.append((None, None, f))
    return rmfiles


def _gc_bytes_to_rmfiles(hsize, files):
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


class HistoryGC(threading.Thread):
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
        self.gc_units_to_rmfiles = {'commands': _gc_commands_to_rmfiles,
                                    'files': _gc_files_to_rmfiles,
                                    's': _gc_seconds_to_rmfiles,
                                    'b': _gc_bytes_to_rmfiles}

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        env = builtins.__xonsh_env__  # pylint: disable=no-member
        if self.size is None:
            hsize, units = env.get('XONSH_HISTORY_SIZE')
        else:
            hsize, units = to_history_tuple(self.size)
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

        This is sorted by the last closed time. Returns a list of (timestamp,
        file) tuples.
        """
        # pylint: disable=no-member
        xdd = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
        xdd = expanduser_abs_path(xdd)

        fs = [f for f in glob.iglob(os.path.join(xdd, 'xonsh-*.json'))]
        files = []
        for f in fs:
            try:
                lj = LazyJSON(f, reopen=False)
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


class HistoryFlusher(threading.Thread):
    """Flush shell history to disk periodically."""

    def __init__(self, filename, buffer, queue, cond, at_exit=False, *args,
                 **kwargs):
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
        """Write the cached history to external storage."""
        with open(self.filename, 'r', newline='\n') as f:
            hist = LazyJSON(f).load()
        hist['cmds'].extend(self.buffer)
        if self.at_exit:
            hist['ts'][1] = time.time()  # apply end time
            hist['locked'] = False
        with open(self.filename, 'w', newline='\n') as f:
            ljdump(hist, f, sort_keys=True)


class CommandField(abc.Sequence):
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
                'CommandField may only be indexed by int or slice.')
        elif size == 0:
            raise IndexError('CommandField is empty.')
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
                lj = LazyJSON(f, reopen=False)
                rtn = lj['cmds'][key].get(self.field, self.default)
                if isinstance(rtn, LJNode):
                    rtn = rtn.load()
            queue.popleft()
        return rtn

    def i_am_at_the_front(self):
        """Tests if the command field is at the front of the queue."""
        return self is self.hist._queue[0]


def _find_histfile_var(file_list, default=None):
    """Return the path of the history file
    from the value of the envvar HISTFILE.
    """
    for f in file_list:
        f = expanduser_abs_path(f)
        if not os.path.isfile(f):
            continue
        with open(f, 'r') as rc_file:
            for line in rc_file:
                if line.startswith('HISTFILE='):
                    hist_file = line.split('=', 1)[1].strip('\'"\n')
                    hist_file = expanduser_abs_path(hist_file)
                    if os.path.isfile(hist_file):
                        return hist_file
    else:
        if default:
            default = expanduser_abs_path(default)
            if os.path.isfile(default):
                return default


def _all_xonsh_parser(**kwargs):
    """
    Returns all history as found in XONSH_DATA_DIR.

    return format: (name, start_time, index)
    """
    data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
    data_dir = expanduser_abs_path(data_dir)

    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
             if f.startswith('xonsh-') and f.endswith('.json')]
    ind = 0
    for f in files:
        try:
            json_file = LazyJSON(f, reopen=False)
        except ValueError:
            # Invalid json file
            pass
        commands = json_file.load()['cmds']
        for c in commands:
            yield (c['inp'].rstrip(), c['ts'][0], ind)
            ind += 1


def _curr_session_parser(hist=None, **kwargs):
    """
    Take in History object and return command list tuple with
    format: (name, start_time, index)
    """
    if hist is None:
        hist = builtins.__xonsh_history__
    start_times = (start for start, end in hist.tss)
    names = (name.rstrip() for name in hist.inps)
    for ind, (c, t) in enumerate(zip(names, start_times)):
        yield (c, t, ind)


def _zsh_hist_parser(location=None, **kwargs):
    """Yield commands from zsh history file"""
    if location is None:
        location = _find_histfile_var([os.path.join('~', '.zshrc'),
                                       os.path.join('~', '.zprofile')],
                                      os.path.join('~', '.zsh_history'))
    if location:
        with open(location, 'r', errors='backslashreplace') as zsh_hist:
            for ind, line in enumerate(zsh_hist):
                if line.startswith(':'):
                    try:
                        start_time, command = line.split(';', 1)
                    except ValueError:
                        # Invalid history entry
                        continue
                    try:
                        start_time = float(start_time.split(':')[1])
                    except ValueError:
                        start_time = 0.0
                    yield (command.rstrip(), start_time, ind)
                else:
                    yield (line.rstrip(), 0.0, ind)

    else:
        print("No zsh history file found", file=sys.stderr)


def _bash_hist_parser(location=None, **kwargs):
    """Yield commands from bash history file"""
    if location is None:
        location = _find_histfile_var([os.path.join('~', '.bashrc'),
                                       os.path.join('~', '.bash_profile')],
                                      os.path.join('~', '.bash_history'))
    if location:
        with open(location, 'r', errors='backslashreplace') as bash_hist:
            for ind, line in enumerate(bash_hist):
                yield (line.rstrip(), 0.0, ind)
    else:
        print("No bash history file", file=sys.stderr)


@functools.lru_cache()
def _hist_create_parser():
    """Create a parser for the "history" command."""
    p = argparse.ArgumentParser(prog='history',
                                description='Tools for dealing with history')
    subp = p.add_subparsers(title='action', dest='action')
    # session action
    show = subp.add_parser('show', prefix_chars='-+',
                           help='displays session history, default action')
    show.add_argument('-r', dest='reverse', default=False,
                      action='store_true', help='reverses the direction')
    show.add_argument('-n', dest='numerate', default=False, action='store_true',
                      help='numerate each command')
    show.add_argument('-t', dest='timestamp', default=False,
                      action='store_true', help='show command timestamps')
    show.add_argument('-T', dest='end_time', default=None,
                      help='show only commands before timestamp')
    show.add_argument('+T', dest='start_time', default=None,
                      help='show only commands after timestamp')
    show.add_argument('-f', dest='datetime_format', default=None,
                      help='the datetime format to be used for filtering and printing')
    show.add_argument('session', nargs='?', choices=_HIST_SESSIONS.keys(), default='session',
                      help='Choose a history session, defaults to current session')
    show.add_argument('slices', nargs='*', default=None,
                      help='display history entries or range of entries')
    # 'id' subcommand
    subp.add_parser('id', help='displays the current session id')
    # 'file' subcommand
    subp.add_parser('file', help='displays the current history filename')
    # 'info' subcommand
    info = subp.add_parser('info', help=('displays information about the '
                                         'current history'))
    info.add_argument('--json', dest='json', default=False,
                      action='store_true', help='print in JSON format')
    # diff
    diff = subp.add_parser('diff', help='diffs two xonsh history files')
    _dh_create_parser(p=diff)
    # replay, dynamically
    from xonsh import replay
    rp = subp.add_parser('replay', help='replays a xonsh history file')
    replay._rp_create_parser(p=rp)
    _HIST_MAIN_ACTIONS['replay'] = replay._rp_main_action
    # gc
    gcp = subp.add_parser(
        'gc', help='launches a new history garbage collector')
    gcp.add_argument('--size', nargs=2, dest='size', default=None,
                     help=('next two arguments represent the history size and '
                           'units; e.g. "--size 8128 commands"'))
    bgcp = gcp.add_mutually_exclusive_group()
    bgcp.add_argument('--blocking', dest='blocking', default=True,
                      action='store_true',
                      help=('ensures that the gc blocks the main thread, '
                            'default True'))
    bgcp.add_argument('--non-blocking', dest='blocking', action='store_false',
                      help='makes the gc non-blocking, and thus return sooner')
    return p


def _hist_get_portion(commands, slices):
    """Yield from portions of history commands."""
    if len(slices) == 1:
        s = slices[0]
        try:
            yield from itertools.islice(commands, s.start, s.stop, s.step)
            return
        except ValueError:  # islice failed
            pass
    commands = list(commands)
    for s in slices:
        yield from commands[s]


def _hist_filter_ts(commands, start_time, end_time):
    """Yield only the commands between start and end time."""
    for cmd in commands:
        if start_time <= cmd[1] < end_time:
            yield cmd


def _hist_get(session='session', *, slices=None, datetime_format=None,
              start_time=None, end_time=None, location=None):
    """Get the requested portion of shell history.

    Parameters
    ----------
    session: {'session', 'all', 'xonsh', 'bash', 'zsh'}
        The history session to get.
    slices : list of slice-like objects, optional
        Get only portions of history.
    start_time, end_time: float, optional
        Filter commands by timestamp.
    location: string, optional
        The history file location (bash or zsh)

    Returns
    -------
    generator
       A filtered list of commands
    """
    cmds = _HIST_SESSIONS[session](location=location)
    if slices:
        # transform/check all slices
        slices = [ensure_slice(s) for s in slices]
        cmds = _hist_get_portion(cmds, slices)
    if start_time or end_time:
        if start_time is None:
            start_time = 0.0
        else:
            start_time = ensure_timestamp(start_time, datetime_format)
        if end_time is None:
            end_time = float('inf')
        else:
            end_time = ensure_timestamp(end_time, datetime_format)
        cmds = _hist_filter_ts(cmds, start_time, end_time)
    return cmds


def _hist_show(ns, *args, **kwargs):
    """Show the requested portion of shell history.
    Accepts same parameters with `_hist_get`.
    """
    try:
        commands = _hist_get(ns.session,
                             slices=ns.slices,
                             start_time=ns.start_time,
                             end_time=ns.end_time,
                             datetime_format=ns.datetime_format)
    except ValueError as err:
        print("history: error: {}".format(err), file=sys.stderr)
        return
    if ns.reverse:
        commands = reversed(list(commands))
    if not ns.numerate and not ns.timestamp:
        for c, _, _ in commands:
            print(c)
    elif not ns.timestamp:
        for c, _, i in commands:
            print('{}: {}'.format(i, c))
    elif not ns.numerate:
        for c, ts, _ in commands:
            dt = datetime.datetime.fromtimestamp(ts).ctime()
            print('({}) {}'.format(dt, c))
    else:
        for c, ts, i in commands:
            dt = datetime.datetime.fromtimestamp(ts).ctime()
            print('{}:({}) {}'.format(i, dt, c))


# Interface to History
class History(object):
    """Xonsh session history.

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
            ljdump(meta, f, sort_keys=True)
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
            Whether the HistoryFlusher should act as a thread in the
            background, or execute immeadiately and block.

        Returns
        -------
        hf : HistoryFlusher or None
            The thread that was spawned to flush history
        """
        if len(self.buffer) == 0:
            return
        hf = HistoryFlusher(self.filename, tuple(self.buffer), self._queue,
                            self._cond, at_exit=at_exit)
        self.buffer.clear()
        return hf

    def show(self, *args, **kwargs):
        """Return shell history as a list

        Valid options:
            `session` - returns xonsh history from current session
            `xonsh`   - returns xonsh history from all sessions
            `zsh`     - returns all zsh history
            `bash`    - returns all bash history
        """
        return list(_hist_get(*args, **kwargs))


def _hist_info(ns, hist):
    """Display information about the shell history."""
    data = collections.OrderedDict()
    data['sessionid'] = str(hist.sessionid)
    data['filename'] = hist.filename
    data['length'] = len(hist)
    data['buffersize'] = hist.buffersize
    data['bufferlength'] = len(hist.buffer)
    if ns.json:
        s = json.dumps(data)
        print(s)
    else:
        lines = ['{0}: {1}'.format(k, v) for k, v in data.items()]
        print('\n'.join(lines))


def _hist_gc(ns, hist):
    """Start and monitor garbage collection of the shell history."""
    hist.gc = gc = HistoryGC(wait_for_shell=False, size=ns.size)
    if ns.blocking:
        while gc.is_alive():
            continue


@lazyobject
def _HIST_SESSIONS():
    return {'session': _curr_session_parser,
            'xonsh': _all_xonsh_parser,
            'all': _all_xonsh_parser,
            'zsh': _zsh_hist_parser,
            'bash': _bash_hist_parser}


@lazyobject
def _HIST_MAIN_ACTIONS():
    return {
        'show': _hist_show,
        'id': lambda ns, hist: print(hist.sessionid),
        'file': lambda ns, hist: print(hist.filename),
        'info': _hist_info,
        'diff': _dh_main_action,
        'gc': _hist_gc,
    }


def _hist_parse_args(args):
    """Prepare and parse arguments for the history command.

    Add default action for ``history`` and
    default session for ``history show``.
    """
    parser = _hist_create_parser()
    if not args:
        args = ['show', 'session']
    elif args[0] not in _HIST_MAIN_ACTIONS and args[0] not in ('-h', '--help'):
        args = ['show', 'session'] + args
    if args[0] == 'show':
        if not any(a in _HIST_SESSIONS for a in args):
            args.insert(1, 'session')
        ns, slices = parser.parse_known_args(args)
        if slices:
            if not ns.slices:
                ns.slices = slices
            else:
                ns.slices.extend(slices)
    else:
        ns = parser.parse_args(args)
    return ns


def history_main(args=None, stdin=None):
    """This is the history command entry point."""
    hist = builtins.__xonsh_history__
    ns = _hist_parse_args(args)
    if ns:
        _HIST_MAIN_ACTIONS[ns.action](ns, hist)
