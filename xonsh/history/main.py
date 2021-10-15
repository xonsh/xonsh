# -*- coding: utf-8 -*-
"""Main entry points of the xonsh history."""
import datetime
import json
import os
import sys
import threading
import typing as tp

from xonsh.built_ins import XSH
import xonsh.cli_utils as xcli
from xonsh.history.base import History
from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory
from xonsh.history.sqlite import SqliteHistory
import xonsh.diff_history as xdh
import xonsh.tools as xt

HISTORY_BACKENDS = {"dummy": DummyHistory, "json": JsonHistory, "sqlite": SqliteHistory}


def construct_history(**kwargs):
    """Construct the history backend object."""
    env = XSH.env
    backend = env.get("XONSH_HISTORY_BACKEND")
    if isinstance(backend, str) and backend in HISTORY_BACKENDS:
        kls_history = HISTORY_BACKENDS[backend]
    elif xt.is_class(backend):
        kls_history = backend
    elif isinstance(backend, History):
        return backend
    else:
        print(
            "Unknown history backend: {}. Using JSON version".format(backend),
            file=sys.stderr,
        )
        kls_history = JsonHistory
    return kls_history(**kwargs)


def _xh_session_parser(hist=None, newest_first=False, **kwargs):
    """Returns history items of current session."""
    if hist is None:
        hist = XSH.history
    return hist.items()


def _xh_all_parser(hist=None, newest_first=False, **kwargs):
    """Returns all history items."""
    if hist is None:
        hist = XSH.history
    return hist.all_items(newest_first=newest_first)


def _xh_find_histfile_var(file_list, default=None):
    """Return the path of the history file
    from the value of the envvar HISTFILE.
    """
    for f in file_list:
        f = xt.expanduser_abs_path(f)
        if not os.path.isfile(f):
            continue
        with open(f, "r") as rc_file:
            for line in rc_file:
                if line.startswith("HISTFILE="):
                    hist_file = line.split("=", 1)[1].strip("'\"\n")
                    hist_file = xt.expanduser_abs_path(hist_file)
                    if os.path.isfile(hist_file):
                        return hist_file
    else:
        if default:
            default = xt.expanduser_abs_path(default)
            if os.path.isfile(default):
                return default


def _xh_bash_hist_parser(location=None, **kwargs):
    """Yield commands from bash history file"""
    if location is None:
        location = _xh_find_histfile_var(
            [os.path.join("~", ".bashrc"), os.path.join("~", ".bash_profile")],
            os.path.join("~", ".bash_history"),
        )
    if location:
        with open(location, "r", errors="backslashreplace") as bash_hist:
            for ind, line in enumerate(bash_hist):
                yield {"inp": line.rstrip(), "ts": 0.0, "ind": ind}
    else:
        print("No bash history file", file=sys.stderr)


def _xh_zsh_hist_parser(location=None, **kwargs):
    """Yield commands from zsh history file"""
    if location is None:
        location = _xh_find_histfile_var(
            [os.path.join("~", ".zshrc"), os.path.join("~", ".zprofile")],
            os.path.join("~", ".zsh_history"),
        )
    if location:
        with open(location, "r", errors="backslashreplace") as zsh_hist:
            for ind, line in enumerate(zsh_hist):
                if line.startswith(":"):
                    try:
                        start_time, command = line.split(";", 1)
                    except ValueError:
                        # Invalid history entry
                        continue
                    try:
                        start_time = float(start_time.split(":")[1])
                    except ValueError:
                        start_time = 0.0
                    yield {"inp": command.rstrip(), "ts": start_time, "ind": ind}
                else:
                    yield {"inp": line.rstrip(), "ts": 0.0, "ind": ind}

    else:
        print("No zsh history file found", file=sys.stderr)


def _xh_filter_ts(commands, start_time, end_time):
    """Yield only the commands between start and end time."""
    for cmd in commands:
        if start_time <= cmd["ts"] < end_time:
            yield cmd


def _xh_get_history(
    session="session",
    *,
    slices=None,
    datetime_format=None,
    start_time=None,
    end_time=None,
    location=None
):
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
    cmds = []
    for i, item in enumerate(_XH_HISTORY_SESSIONS[session](location=location)):
        item["ind"] = i
        cmds.append(item)
    if slices:
        # transform/check all slices
        slices = [xt.ensure_slice(s) for s in slices]
        cmds = xt.get_portions(cmds, slices)
    if start_time or end_time:
        if start_time is None:
            start_time = 0.0
        else:
            start_time = xt.ensure_timestamp(start_time, datetime_format)
        if end_time is None:
            end_time = float("inf")
        else:
            end_time = xt.ensure_timestamp(end_time, datetime_format)
        cmds = _xh_filter_ts(cmds, start_time, end_time)
    return cmds


_XH_HISTORY_SESSIONS = {
    "session": _xh_session_parser,
    "xonsh": _xh_all_parser,
    "all": _xh_all_parser,
    "zsh": _xh_zsh_hist_parser,
    "bash": _xh_bash_hist_parser,
}


class HistoryAlias(xcli.ArgParserAlias):
    """Try 'history <command> --help' for more info"""

    def show(
        self,
        session: xcli.Annotated[
            str, xcli.Arg(nargs="?", choices=tuple(_XH_HISTORY_SESSIONS))
        ] = "session",
        slices: xcli.Annotated[tp.List[int], xcli.Arg(nargs="*")] = None,
        datetime_format: tp.Optional[str] = None,
        start_time: tp.Optional[str] = None,
        end_time: tp.Optional[str] = None,
        location: tp.Optional[str] = None,
        reverse=False,
        numerate=False,
        timestamp=False,
        null_byte=False,
        _stdout=None,
        _stderr=None,
        _unparsed=None,
    ):
        """Display history of a session, default command

        Parameters
        ----------
        session:
            The history session to get. (all is an alias for xonsh)
        slices:
            integer or slice notation to get only portions of history.
        datetime_format : -f
            the datetime format to be used for filtering and printing
        start_time: --start-time, +T
            show only commands after timestamp
        end_time: -T, --end-time
            show only commands before timestamp
        location: -l, --location
            The history file location (bash or zsh)
        reverse: -r, --reverse
            Reverses the direction
        numerate: -n, --numerate
            Numerate each command
        timestamp: -t, --ts, --time-stamp
            show command timestamps
        null_byte: -0, --nb, --null-byte
            separate commands by the null character for piping history to external filters
        _unparsed
            remaining args from ``parser.parse_known_args``
        """
        slices = list(slices or ())
        if _unparsed:
            slices.extend(_unparsed)
        try:
            commands = _xh_get_history(
                session,
                slices=slices,
                start_time=start_time,
                end_time=end_time,
                datetime_format=datetime_format,
                location=location,
            )
        except Exception as err:
            self.parser.error(err)
            return

        if reverse:
            commands = reversed(list(commands))
        end = "\0" if null_byte else "\n"
        if numerate and timestamp:
            for c in commands:
                dt = datetime.datetime.fromtimestamp(c["ts"])
                print(
                    "{}:({}) {}".format(c["ind"], xt.format_datetime(dt), c["inp"]),
                    file=_stdout,
                    end=end,
                )
        elif numerate:
            for c in commands:
                print("{}: {}".format(c["ind"], c["inp"]), file=_stdout, end=end)
        elif timestamp:
            for c in commands:
                dt = datetime.datetime.fromtimestamp(c["ts"])
                print(
                    "({}) {}".format(xt.format_datetime(dt), c["inp"]),
                    file=_stdout,
                    end=end,
                )
        else:
            for c in commands:
                print(c["inp"], file=_stdout, end=end)

    @staticmethod
    def id_cmd(_stdout):
        """Display the current session id"""
        hist = XSH.history
        if not hist.sessionid:
            return
        print(str(hist.sessionid), file=_stdout)

    @staticmethod
    def flush(_stdout):
        """Flush the current history to disk"""

        hist = XSH.history
        hf = hist.flush()
        if isinstance(hf, threading.Thread):
            hf.join()

    @staticmethod
    def off():
        """History will not be saved for this session"""
        hist = XSH.history
        if hist.remember_history:
            hist.clear()
            hist.remember_history = False
            print("History off", file=sys.stderr)

    @staticmethod
    def on():
        """History will be saved for the rest of the session (default)"""
        hist = XSH.history
        if not hist.remember_history:
            hist.remember_history = True
            print("History on", file=sys.stderr)

    @staticmethod
    def clear():
        """One-time wipe of session history"""
        hist = XSH.history
        hist.clear()
        print("History cleared", file=sys.stderr)

    @staticmethod
    def file(_stdout):
        """Display the current history filename"""
        hist = XSH.history
        if not hist.filename:
            return
        print(str(hist.filename), file=_stdout)

    @staticmethod
    def info(
        to_json=False,
        _stdout=None,
    ):
        """Display information about the current history

        Parameters
        ----------
        to_json: -j, --json
            print in JSON format
        """
        hist = XSH.history

        data = hist.info()
        if to_json:
            s = json.dumps(data)
            print(s, file=_stdout)
        else:
            lines = ["{0}: {1}".format(k, v) for k, v in data.items()]
            print("\n".join(lines), file=_stdout)

    @staticmethod
    def gc(
        size: xcli.Annotated[tp.Tuple[int, str], xcli.Arg(nargs=2)] = None,
        force=False,
        _blocking=True,
    ):
        """Launches a new history garbage collector

        Parameters
        ----------
        size : -s, --size
            Next two arguments represent the history size and units; e.g. "--size 8128 commands"
        force : -f, --force
            perform garbage collection even if history much bigger than configured limit
        """
        hist = XSH.history
        hist.run_gc(size=size, blocking=_blocking, force=force)

    @staticmethod
    def diff(
        a,
        b,
        reopen=False,
        verbose=False,
        _stdout=None,
    ):
        """Diff two xonsh history files

        Parameters
        ----------
        left:
            The first file to diff
        right:
            The second file to diff
        reopen: -r, --reopen
            make lazy file loading reopen files each time
        verbose: -v, --verbose
            whether to print even more information
        """

        hist = XSH.history
        if isinstance(hist, JsonHistory):
            hd = xdh.HistoryDiffer(a, b, reopen=reopen, verbose=verbose)
            xt.print_color(hd.format(), file=_stdout)

    def build(self):
        parser = self.create_parser(prog="history")
        parser.add_command(self.show, prefix_chars="-+")
        parser.add_command(self.id_cmd, prog="id")
        parser.add_command(self.file)
        parser.add_command(self.info)
        parser.add_command(self.flush)
        parser.add_command(self.off)
        parser.add_command(self.on)
        parser.add_command(self.clear)

        gcp = parser.add_command(self.gc)
        bgcp = gcp.add_mutually_exclusive_group()
        bgcp.add_argument(
            "--blocking",
            dest="_blocking",
            default=True,
            action="store_true",
            help="ensures that the gc blocks the main thread, default True",
        )
        bgcp.add_argument(
            "--non-blocking",
            dest="_blocking",
            action="store_false",
            help="makes the gc non-blocking, and thus return sooner",
        )
        if isinstance(XSH.history, JsonHistory):
            # add actions belong only to JsonHistory
            parser.add_command(self.diff)

        return parser

    def __call__(self, args, *rest, **kwargs):
        if not args:
            args = ["show", "session"]
        else:
            actions = self.parser.commands.choices
            cmd = args[0]
            if cmd not in actions and cmd not in {"-h", "--help"}:
                args = ["show", "session"] + args

        if args[0] == "show":
            if not any(a in _XH_HISTORY_SESSIONS for a in args):
                args.insert(1, "session")

            kwargs.setdefault("lenient", True)
        return super().__call__(args, *rest, **kwargs)


history_main = HistoryAlias()
