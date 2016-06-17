# -*- coding: utf-8 -*-
"""Implements the xonsh history object."""
import os
import sys
import argparse
import functools
import operator
import uuid
import time
import datetime
import builtins
from glob import iglob
from collections import deque, Sequence, OrderedDict
from threading import Thread, Condition

from xonsh.lazyjson import LazyJSON, ljdump, LJNode
from xonsh.tools import (ensure_int_or_slice, to_history_tuple,
                         expanduser_abs_path)
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


class HistoryGC(Thread):
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
        _ = self  # this could be a function but is intimate to this class
        # pylint: disable=no-member
        xdd = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
        xdd = expanduser_abs_path(xdd)

        fs = [f for f in iglob(os.path.join(xdd, 'xonsh-*.json'))]
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


class HistoryFlusher(Thread):
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


class CommandField(Sequence):
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


def _find_histfile_var(file_list=None, default=None):
    if file_list is None:
        return None
    hist_file = None

    found_hist = False
    for f in file_list:
        f = expanduser_abs_path(f)
        if not os.path.isfile(f):
            continue
        with open(f, 'r') as rc_file:
            for line in rc_file:
                if "HISTFILE=" in line:
                    evar = line.split(' ', 1)[-1]
                    hist_file = evar.split('=', 1)[-1]
                    for char in ['"', "'", '\n']:
                        hist_file = hist_file.replace(char, '')
                    hist_file = expanduser_abs_path(hist_file)
                    if os.path.isfile(hist_file):
                        found_hist = True
                        break
        if found_hist:
            break

    if hist_file is None:
        default = expanduser_abs_path(default)
        if os.path.isfile(default):
            hist_file = default

    return hist_file


def _all_xonsh_parser(*args):
    """
    Returns all history as found in XONSH_DATA_DIR.

    return format: (name, start_time, index)
    """
    data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
    data_dir = expanduser_abs_path(data_dir)

    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
             if f.startswith('xonsh-') and f.endswith('.json')]
    file_hist = []
    for f in files:
        try:
            json_file = LazyJSON(f, reopen=False)
            file_hist.append(json_file.load()['cmds'])
        except ValueError:
            # Invalid json file
            pass
    commands = [(c['inp'][:-1] if c['inp'].endswith('\n') else c['inp'],
                 c['ts'][0])
                for commands in file_hist for c in commands if c]
    commands.sort(key=operator.itemgetter(1))
    return [(c, t, ind) for ind, (c, t) in enumerate(commands)]


def _curr_session_parser(hist=None):
    """
    Take in History object and return command list tuple with
    format: (name, start_time, index)
    """
    if hist is None:
        hist = builtins.__xonsh_history__
    if not hist:
        return None
    start_times = [start for start, end in hist.tss]
    names = [name[:-1] if name.endswith('\n') else name
             for name in hist.inps]
    commands = enumerate(zip(names, start_times))
    return [(c, t, ind) for ind, (c, t) in commands]


def _zsh_hist_parser(location=None):
    default_location = os.path.join('~', '.zsh_history')
    location_list = [os.path.join('~', '.zshrc'),
                     os.path.join('~', '.zprofile')]
    if location is None:
        location = _find_histfile_var(location_list, default_location)
    z_hist_formatted = []
    if os.path.isfile(location):
        with open(location, 'r', errors='backslashreplace') as z_file:
            z_txt = z_file.read()
            z_hist = z_txt.splitlines()
            if z_hist:
                for ind, line in enumerate(z_hist):
                    try:
                        start_time, command = line.split(';', 1)
                    except ValueError:
                        # Invalid history entry
                        continue
                    try:
                        start_time = float(start_time.split(':')[1])
                    except ValueError:
                        start_time = -1
                    z_hist_formatted.append((command, start_time, ind))
                return z_hist_formatted

    else:
        print("No zsh history file found at: {}".format(location),
              file=sys.stderr)


def _bash_hist_parser(location=None):
    default_location = os.path.join('~', '.bash_history')
    location_list = [os.path.join('~', '.bashrc'),
                     os.path.join('~', '.bash_profile')]
    if location is None:
        location = _find_histfile_var(location_list, default_location)
    bash_hist_formatted = []
    if os.path.isfile(location):
        with open(location, 'r', errors='backslashreplace') as bash_file:
            b_txt = bash_file.read()
            bash_hist = b_txt.splitlines()
            if bash_hist:
                for ind, command in enumerate(bash_hist):
                    bash_hist_formatted.append((command, 0.0, ind))
                return bash_hist_formatted
    else:
        import ipdb
        ipdb.set_trace()
        print("No bash history file found at: {}".format(location),
              file=sys.stderr)


@functools.lru_cache()
def _hist_create_parser():
    """Create a parser for the "history" command."""
    p = argparse.ArgumentParser(prog='history',
                                description='Tools for dealing with history')
    subp = p.add_subparsers(title='action', dest='action')
    # session action
    show = subp.add_parser('show', aliases=['session'],
                           help='displays session history, default action')
    show.add_argument('-r', dest='reverse', default=False,
                      action='store_true',
                      help='reverses the direction')
    show.add_argument('n', nargs='?', default=None,
                      help='display n\'th history entry if n is a simple '
                           'int, or range of entries if it is Python '
                           'slice notation')
    # all action
    xonsh = subp.add_parser('xonsh', aliases=['all'],
                            help='displays history from all sessions')
    xonsh.add_argument('-r', dest='reverse', default=False,
                       action='store_true',
                       help='reverses the direction')
    xonsh.add_argument('n', nargs='?', default=None,
                       help='display n\'th history entry if n is a '
                            'simple int, or range of entries if it '
                            'is Python slice notation')
    # zsh action
    zsh = subp.add_parser('zsh', help='displays history from zsh sessions')
    zsh.add_argument('-r', dest='reverse', default=False,
                     action='store_true',
                     help='reverses the direction')
    zsh.add_argument('n', nargs='?', default=None,
                     help='display n\'th history entry if n is a '
                     'simple int, or range of entries if it '
                     'is Python slice notation')
    # bash action
    bash = subp.add_parser('bash', help='displays history from bash sessions')
    bash.add_argument('-r', dest='reverse', default=False,
                      action='store_true',
                      help='reverses the direction')
    bash.add_argument('n', nargs='?', default=None,
                      help='display n\'th history entry if n is a '
                      'simple int, or range of entries if it '
                      'is Python slice notation')
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


def _show(ns=None, hist=None, start_index=None, end_index=None,
          start_time=None, end_time=None, location=None):
    """
    Show the requested portion of shell history.
    Accepts multiple history sources (xonsh, bash, zsh)

    May be invoked as an alias with `history all/bash/zsh` which will
    provide history as stdout or with `__xonsh_history__.show()`
    which will return the history as a list with each item
    in the tuple form (name, start_time, index).

    If invoked via __xonsh_history__.show() then the ns parameter
    can be supplied as a str with the follow options:
        `session` - returns xonsh history from current session
        `all`     - returns xonsh history from all sessions
        `zsh`     - returns all zsh history
        `bash`    - returns all bash history
    """
    # Check if ns is a string, meaning it was invoked from
    # __xonsh_history__
    alias = True
    valid_formats = {'session': functools.partial(_curr_session_parser, hist),
                     'show': functools.partial(_curr_session_parser, hist),
                     'all': _all_xonsh_parser,
                     'xonsh': _all_xonsh_parser,
                     'zsh': functools.partial(_zsh_hist_parser, location),
                     'bash': functools.partial(_bash_hist_parser, location)}
    if isinstance(ns, str) and ns in valid_formats.keys():
        ns = _hist_create_parser().parse_args([ns])
        alias = False
    if not ns:
        ns = _hist_create_parser().parse_args(['all'])
        alias = False
    try:
        commands = valid_formats[ns.action]()
    except KeyError:
        print("{} is not a valid history format".format(ns.action))
        return None
    if not commands:
        return None
    if start_time:
        if isinstance(start_time, datetime.datetime):
            start_time = start_time.timestamp()
        if isinstance(start_time, float):
            commands = [c for c in commands if c[1] >= start_time]
        else:
            print("Invalid start time, must be float or datetime.")
    if end_time:
        if isinstance(end_time, datetime.datetime):
            end_time = end_time.timestamp()
        if isinstance(end_time, float):
            commands = [c for c in commands if c[1] <= end_time]
        else:
            print("Invalid end time, must be float or datetime.")
    idx = None
    if ns:
        idx = ensure_int_or_slice(ns.n)
        if idx is False:
            print("{} is not a valid input.".format(ns.n),
                  file=sys.stderr)
            return
        elif isinstance(idx, int):
            try:
                commands = [commands[idx]]
            except IndexError:
                err = "Index likely not in range. Only {} commands."
                print(err.format(len(commands)))
                return
    else:
        idx = slice(start_index, end_index)

    if (isinstance(idx, slice) and
            start_time is None and end_time is None):
        commands = commands[idx]

    if ns and ns.reverse:
        commands = list(reversed(commands))

    if commands:
        digits = len(str(max([i for c, t, i in commands])))
        if alias:
            for c, t, i in commands:
                for line_ind, line in enumerate(c.split('\n')):
                    if line_ind == 0:
                        print('{:>{width}}: {}'.format(i, line,
                                                       width=digits + 1))
                    else:
                        print(' {:>>{width}} {}'.format('', line,
                                                        width=digits + 1))
        else:
            return commands


#
# Interface to History
#
class History(object):
    """Xonsh session history."""

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
        self._queue = deque()
        self._cond = Condition()
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
        """
        Returns shell history as a list

        Valid options:
            `session` - returns xonsh history from current session
            `show`    - alias of `session`
            `all`     - returns xonsh history from all sessions
            `xonsh`   - alias of `all`
            `zsh`     - returns all zsh history
            `bash`    - returns all bash history
        """
        return _show(*args, **kwargs)


def _info(ns, hist):
    """Display information about the shell history."""
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
    """Start and monitor garbage collection of the shell history."""
    hist.gc = gc = HistoryGC(wait_for_shell=False, size=ns.size)
    if ns.blocking:
        while gc.is_alive():
            continue


_HIST_MAIN_ACTIONS = {
    'show': _show,
    'xonsh': _show,
    'zsh': _show,
    'bash': _show,
    'session': _show,
    'all': _show,
    'id': lambda ns, hist: print(hist.sessionid),
    'file': lambda ns, hist: print(hist.filename),
    'info': _info,
    'diff': _dh_main_action,
    'gc': _gc,
    }


def _hist_main(hist, args):
    """This implements the history CLI."""
    if not args or args[0] in ['-r'] or ensure_int_or_slice(args[0]):
        args.insert(0, 'show')
    elif args[0] not in list(_HIST_MAIN_ACTIONS) + ['-h', '--help']:
        print("{} is not a valid input.".format(args[0]),
              file=sys.stderr)
        return
    if (args[0] in ['show', 'xonsh', 'zsh', 'bash', 'session', 'all'] and
        len(args) > 1 and args[-1].startswith('-') and
            args[-1][1].isdigit()):
        args.insert(-1, '--')  # ensure parsing stops before a negative int
    ns = _hist_create_parser().parse_args(args)
    if ns.action is None:  # apply default action
        ns = _hist_create_parser().parse_args(['show'] + args)
    _HIST_MAIN_ACTIONS[ns.action](ns, hist)


def history_main(args=None, stdin=None):
    """This is the history command entry point."""
    _ = stdin
    _hist_main(builtins.__xonsh_history__, args)  # pylint: disable=no-member
