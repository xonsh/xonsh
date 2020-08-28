# -*- coding: utf-8 -*-
"""Implements JSON version of xonsh history backend."""
import os
import sys
import time
import json
import builtins
import collections
import threading
import collections.abc as cabc

from xonsh.history.base import History
import xonsh.tools as xt
import xonsh.lazyjson as xlj
import xonsh.xoreutils.uptime as uptime


def _xhj_gc_commands_to_rmfiles(hsize, files) -> ([], int):
    """Return number of units and list of history files to remove to get under the limit,

    Parameters:
    -----------
    hsize (int):  units of history, # of commands in this case.
    files ((mod_ts, num_commands, path)[], fsize): history files, sorted oldest first.

    Returns:
    --------
    hsize_removed (int):  units of history to be removed
    rm_files ((mod_ts, num_commands, path, fsize)[]): list of files to remove.
    """
    n = 0
    ncmds = 0
    for _, fcmds, f, _ in reversed(files):
        # `files` comes in with empty files included (now), don't need special handling to gc them here.

        if ncmds + fcmds > hsize:
            break
        ncmds += fcmds
        n += 1

    cmds_removed = 0
    files_removed = files[:-n]
    for _, fcmds, f, _ in files_removed:
        cmds_removed += fcmds

    return cmds_removed, files_removed


def _xhj_gc_files_to_rmfiles(hsize, files):
    """Return the number and list of history files to remove to get under the file limit."""
    rmfiles = files[:-hsize] if len(files) > hsize else []
    return len(rmfiles), rmfiles


def _xhj_gc_seconds_to_rmfiles(hsize, files):
    """Return age removed (the age of the *oldest* file) and list of history files to remove to get under the age limit."""
    now = time.time()
    oldest_ts = files[0][0]
    n = 0

    for ts, _, f, _ in files:
        if (now - ts) < hsize:
            break
        n += 1

    return (now - oldest_ts) if n > 0 else 0, files[:n]


def _xhj_gc_bytes_to_rmfiles(hsize, files):
    """Return the history files to remove to get under the byte limit."""
    n = 0
    nbytes = 0
    for _, _, f, fsize in reversed(files):
        if nbytes + fsize > hsize:
            break
        nbytes += fsize
        n += 1
    bytes_removed = 0
    files_removed = files[:-n]
    for _, _, f, fsize in files_removed:
        bytes_removed += fsize

    return bytes_removed, files_removed


def _xhj_get_history_files(sort=True, newest_first=False):
    """Find and return the history files. Optionally sort files by
    modify time.
    """
    data_dir = builtins.__xonsh__.env.get("XONSH_DATA_DIR")
    data_dir = xt.expanduser_abs_path(data_dir)
    try:
        files = [
            os.path.join(data_dir, f)
            for f in os.listdir(data_dir)
            if f.startswith("xonsh-") and f.endswith(".json")
        ]
    except OSError:
        files = []
        if builtins.__xonsh__.env.get("XONSH_DEBUG"):
            xt.print_exception("Could not collect xonsh history files.")
    if sort:
        files.sort(key=lambda x: os.path.getmtime(x), reverse=newest_first)
    return files


class JsonHistoryGC(threading.Thread):
    """Shell history garbage collection."""

    def __init__(self, wait_for_shell=True, size=None, force=False, *args, **kwargs):
        """Thread responsible for garbage collecting old history.

        May wait for shell (and for xonshrc to have been loaded) to start work.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.size = size
        self.wait_for_shell = wait_for_shell
        self.force_gc = force
        self.gc_units_to_rmfiles = {
            "commands": _xhj_gc_commands_to_rmfiles,
            "files": _xhj_gc_files_to_rmfiles,
            "s": _xhj_gc_seconds_to_rmfiles,
            "b": _xhj_gc_bytes_to_rmfiles,
        }
        self.start()

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        env = builtins.__xonsh__.env  # pylint: disable=no-member
        xonsh_debug = env.get("XONSH_DEBUG", 0)
        if self.size is None:
            hsize, units = env.get("XONSH_HISTORY_SIZE")
        else:
            hsize, units = xt.to_history_tuple(self.size)
        files = self.files(only_unlocked=True)
        rmfiles_fn = self.gc_units_to_rmfiles.get(units)
        if rmfiles_fn is None:
            raise ValueError("Units type {0!r} not understood".format(units))

        size_over, rm_files = rmfiles_fn(hsize, files)
        hist = getattr(builtins.__xonsh__, "history", None)
        if hist is not None:  # remember last gc pass history size
            hist.hist_size = size_over + hsize
            hist.hist_units = units

        if self.force_gc or size_over < hsize:
            i = 0
            for _, _, f, _ in rm_files:
                try:
                    os.remove(f)
                    if xonsh_debug:
                        print(
                            f"... Deleted {i:7d} of {len(rm_files):7d} history files.\r",
                            end="",
                        )
                    pass
                except OSError:
                    pass
                i += 1
        else:
            print(
                f"Warning: History garbage collection would discard more history ({size_over} {units}) than it would keep ({hsize}).\n"
                "Not removing any history for now. Either increase your limit ($XONSH_HISTORY_SIZE), or run `history gc --force`."
            )

    def files(self, only_unlocked=False):
        """Find and return the history files. Optionally locked files may be
        excluded.

        This is sorted by the last closed time. Returns a list of
        (file_size, timestamp, number of cmds, file name) tuples.
        """
        env = getattr(getattr(builtins, "__xonsh__", None), "env", None)
        if env is None:
            return []

        xonsh_debug = env.get("XONSH_DEBUG", 0)
        boot = uptime.boottime()
        fs = _xhj_get_history_files(sort=False)
        files = []
        for f in fs:
            try:
                cur_file_size = os.path.getsize(f)
                if cur_file_size == 0:
                    # collect empty files (for gc)
                    files.append((os.path.getmtime(f), 0, f, cur_file_size))
                    continue
                lj = xlj.LazyJSON(f, reopen=False)
                if lj.get("locked", False) and lj["ts"][0] < boot:
                    # computer was rebooted between when this history was created
                    # and now and so this history should be unlocked.
                    hist = lj.load()
                    lj.close()
                    hist["locked"] = False
                    with open(f, "w", newline="\n") as fp:
                        xlj.ljdump(hist, fp, sort_keys=True)
                    lj = xlj.LazyJSON(f, reopen=False)
                if only_unlocked and lj.get("locked", False):
                    continue
                # info: file size, closing timestamp, number of commands, filename
                ts = lj.get("ts", (0.0, None))
                files.append(
                    (ts[1] or ts[0], len(lj.sizes["cmds"]) - 1, f, cur_file_size,),
                )
                lj.close()
                if xonsh_debug:
                    print(f"... Enumerated {len(files):7d} history files.\r", end="")
            except (IOError, OSError, ValueError):
                continue
        files.sort()  # this sorts by elements of the tuple,
        # the first of which just happens to be file mod time.
        # so sort by oldest first.
        return files


class JsonHistoryFlusher(threading.Thread):
    """Flush shell history to disk periodically."""

    def __init__(
        self, filename, buffer, queue, cond, at_exit=False, skip=None, *args, **kwargs
    ):
        """Thread for flushing history."""
        super(JsonHistoryFlusher, self).__init__(*args, **kwargs)
        self.filename = filename
        self.buffer = buffer
        self.queue = queue
        queue.append(self)
        self.cond = cond
        self.at_exit = at_exit
        self.skip = skip
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
        opts = builtins.__xonsh__.env.get("HISTCONTROL")
        last_inp = None
        cmds = []
        for cmd in self.buffer:
            if "ignoredups" in opts and cmd["inp"] == last_inp:
                # Skipping dup cmd
                if self.skip is not None:
                    self.skip(1)
                continue
            if "ignoreerr" in opts and cmd["rtn"] != 0:
                # Skipping failed cmd
                if self.skip is not None:
                    self.skip(1)
                continue
            cmds.append(cmd)
            last_inp = cmd["inp"]
        with open(self.filename, "r", newline="\n") as f:
            hist = xlj.LazyJSON(f).load()
        load_hist_len = len(hist["cmds"])
        hist["cmds"].extend(cmds)
        if self.at_exit:
            hist["ts"][1] = time.time()  # apply end time
            hist["locked"] = False
        if not builtins.__xonsh__.env.get("XONSH_STORE_STDOUT", False):
            [cmd.pop("out") for cmd in hist["cmds"][load_hist_len:] if "out" in cmd]
        with open(self.filename, "w", newline="\n") as f:
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
            raise IndexError("JsonCommandField may only be indexed by int or slice.")
        elif size == 0:
            raise IndexError("JsonCommandField is empty.")
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
            with open(self.hist.filename, "r", newline="\n") as f:
                lj = xlj.LazyJSON(f, reopen=False)
                rtn = lj["cmds"][key].get(self.field, self.default)
                if isinstance(rtn, xlj.LJNode):
                    rtn = rtn.load()
            queue.popleft()
        return rtn

    def i_am_at_the_front(self):
        """Tests if the command field is at the front of the queue."""
        return self is self.hist._queue[0]


class JsonHistory(History):
    """Xonsh history backend implemented with JSON files.

    JsonHistory implements an extra action: ``diff``
    """

    def __init__(self, filename=None, sessionid=None, buffersize=100, gc=True, **meta):
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
        super().__init__(sessionid=sessionid, **meta)
        if filename is None:
            # pylint: disable=no-member
            data_dir = builtins.__xonsh__.env.get("XONSH_DATA_DIR")
            data_dir = os.path.expanduser(data_dir)
            self.filename = os.path.join(
                data_dir, "xonsh-{0}.json".format(self.sessionid)
            )
        else:
            self.filename = filename
        self.buffer = []
        self.buffersize = buffersize
        self._queue = collections.deque()
        self._cond = threading.Condition()
        self._len = 0
        self._skipped = 0
        self.last_cmd_out = None
        self.last_cmd_rtn = None
        meta["cmds"] = []
        meta["sessionid"] = str(self.sessionid)
        with open(self.filename, "w", newline="\n") as f:
            xlj.ljdump(meta, f, sort_keys=True)
        self.gc = JsonHistoryGC() if gc else None
        # command fields that are known
        self.tss = JsonCommandField("ts", self)
        self.inps = JsonCommandField("inp", self)
        self.outs = JsonCommandField("out", self)
        self.rtns = JsonCommandField("rtn", self)

    def __len__(self):
        return self._len - self._skipped

    def append(self, cmd):
        """Appends command to history. Will periodically flush the history to file.

        Parameters
        ----------
        cmd : dict
            This dict contains information about the command that is to be
            added to the history list. It should contain the keys ``inp``,
            ``rtn`` and ``ts``. These key names mirror the same names defined
            as instance variables in the ``HistoryEntry`` class.

        Returns
        -------
        hf : JsonHistoryFlusher or None
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
            Whether the JsonHistoryFlusher should act as a thread in the
            background, or execute immediately and block.

        Returns
        -------
        hf : JsonHistoryFlusher or None
            The thread that was spawned to flush history
        """
        if len(self.buffer) == 0:
            return

        def skip(num):
            self._skipped += num

        hf = JsonHistoryFlusher(
            self.filename,
            tuple(self.buffer),
            self._queue,
            self._cond,
            at_exit=at_exit,
            skip=skip,
        )
        self.buffer = []
        return hf

    def items(self, newest_first=False):
        """Display history items of current session."""
        if newest_first:
            items = zip(reversed(self.inps), reversed(self.tss))
        else:
            items = zip(self.inps, self.tss)
        for item, tss in items:
            yield {"inp": item.rstrip(), "ts": tss[0]}

    def all_items(self, newest_first=False, **kwargs):
        """
        Returns all history as found in XONSH_DATA_DIR.

        yield format: {'inp': cmd, 'rtn': 0, ...}
        """
        while self.gc and self.gc.is_alive():
            time.sleep(0.011)  # gc sleeps for 0.01 secs, sleep a beat longer
        for f in _xhj_get_history_files(newest_first=newest_first):
            try:
                json_file = xlj.LazyJSON(f, reopen=False)
            except ValueError:
                # Invalid json file
                continue
            try:
                commands = json_file.load()["cmds"]
            except json.decoder.JSONDecodeError:
                # file is corrupted somehow
                if builtins.__xonsh__.env.get("XONSH_DEBUG") > 0:
                    msg = "xonsh history file {0!r} is not valid JSON"
                    print(msg.format(f), file=sys.stderr)
                continue
            if newest_first:
                commands = reversed(commands)
            for c in commands:
                yield {"inp": c["inp"].rstrip(), "ts": c["ts"][0]}
        # all items should also include session items
        yield from self.items()

    def info(self):
        data = collections.OrderedDict()
        data["backend"] = "json"
        data["sessionid"] = str(self.sessionid)
        data["filename"] = self.filename
        data["length"] = len(self)
        data["buffersize"] = self.buffersize
        data["bufferlength"] = len(self.buffer)
        envs = builtins.__xonsh__.env
        data["gc options"] = envs.get("XONSH_HISTORY_SIZE")
        data["gc_last_size"] = f"{(self.hist_size, self.hist_units)}"
        return data

    def run_gc(self, size=None, blocking=True, force=False):
        self.gc = JsonHistoryGC(wait_for_shell=False, size=size, force=force)
        if blocking:
            while self.gc.is_alive():  # while waiting for gc.
                time.sleep(0.1)  # don't monopolize the thread (or Python GIL?)
