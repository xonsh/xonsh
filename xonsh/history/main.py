"""Main entry points of the xonsh history."""

import argparse as ap
import datetime
import json
import os
import sys
import threading
import typing as tp

import xonsh.cli_utils as xcli
import xonsh.history.diff_history as xdh
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.history.base import History
from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory

HISTORY_BACKENDS = {"dummy": DummyHistory, "json": JsonHistory}

try:
    from xonsh.history.sqlite import SqliteHistory

    HISTORY_BACKENDS |= {"sqlite": SqliteHistory}
except Exception:
    """
    On some linux systems (e.g. alt linux) sqlite3 is not installed
    and it's hard to install it and maybe user can't install it.
    We need to just go forward.
    """
    pass


def construct_history(backend=None, **kwargs) -> "History":
    """Construct the history backend object."""
    env = XSH.env
    backend = backend or env.get("XONSH_HISTORY_BACKEND", "json")
    if isinstance(backend, str) and backend in HISTORY_BACKENDS:
        kls_history = HISTORY_BACKENDS[backend]
    elif xt.is_class(backend):
        kls_history = backend
    elif isinstance(backend, History):
        return backend
    else:
        print(
            f"Unknown history backend: {backend}. Using JSON version",
            file=sys.stderr,
        )
        kls_history = JsonHistory

    try:
        return kls_history(**kwargs)
    except Exception as e:
        xt.print_exception(
            f"Error during load {kls_history}: {e}\n"
            f"Set $XONSH_HISTORY_BACKEND='dummy' to disable history.\n"
            f"History disabled."
        )
        return DummyHistory()


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
        with open(f) as rc_file:
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
        try:
            with open(location, errors="backslashreplace") as bash_hist:
                for ind, line in enumerate(bash_hist):
                    yield {"inp": line.rstrip(), "ts": 0.0, "ind": ind}
        except PermissionError:
            print(f"Bash history permission error in {location!r}", file=sys.stderr)
            yield {
                "inp": f"# Bash history permission error in {location!r}",
                "ts": 0.0,
                "ind": 0,
            }
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
        with open(location, errors="backslashreplace") as zsh_hist:
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
    location=None,
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


class SessionAction(ap.Action):
    """Set the choices lazily"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", tuple(_XH_HISTORY_SESSIONS))
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string: "str | None" = None):
        setattr(namespace, self.dest, values)


class HistoryAlias(xcli.ArgParserAlias):
    """Try 'history <command> --help' for more info"""

    def show(
        self,
        session: xcli.Annotated[
            str, xcli.Arg(nargs="?", action=SessionAction)
        ] = "session",
        slices: xcli.Annotated[list[int], xcli.Arg(nargs="*")] = None,
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
    def pull(show_commands=False, _stdout=None):
        """Pull history from other parallel sessions.

        Parameters
        ----------
        show_commands: -c, --show-commands
            show pulled commands
        """

        hist = XSH.history

        if hist.pull.__module__ == "xonsh.history.base":
            backend = XSH.env.get("XONSH_HISTORY_BACKEND", "unknown")
            print(
                f"Pull method is not supported in {backend} history backend.",
                file=_stdout,
            )

        lines_added = hist.pull(show_commands)
        if lines_added:
            print(f"Added {lines_added} records!", file=_stdout)
        else:
            print("No records found!", file=_stdout)

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
    def delete(pattern):
        """Delete all commands matching a pattern

        Parameters
        ----------
        pattern:
            regex pattern to match against command history
        """
        hist = XSH.history
        deleted = hist.delete(pattern)
        print(f"Deleted {deleted} entries from history")

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
            lines = [f"{k}: {v}" for k, v in data.items()]
            print("\n".join(lines), file=_stdout)

    @staticmethod
    def gc(
        size: xcli.Annotated[tuple[int, str], xcli.Arg(nargs=2)] = None,
        force=False,
        blocking=True,
    ):
        """Launches a new history garbage collector

        Parameters
        ----------
        size : -s, --size
            Next two arguments represent the history size and units; e.g. "--size 8128 commands"
        force : -f, --force
            perform garbage collection even if history much bigger than configured limit
        blocking : -n, --non-blocking
            makes the gc non-blocking, and thus return sooner. By default it runs on main thread blocking input.
        """
        hist = XSH.history
        hist.run_gc(size=size, blocking=blocking, force=force)

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

    def transfer(
        self,
        source: tp.Annotated[str, xcli.Arg(action=SessionAction)],
        source_file: "str|None" = None,
        target: tp.Annotated["str | None", xcli.Arg(action=SessionAction)] = None,
        target_file: "str|None" = None,
    ):
        """Transfer entries between history backends.

        Parameters
        ----------
        source
            Name of the source history backend
        source_file : --source-file, --sf
            Override the default location of the history file of the backend.
        target : --target, -t
            Name of the target history backend. (default: $XONSH_HISTORY_BACKEND)
        target_file : --target-file, --tf
            Path to the location of the history file.

        Notes
        -----
        It will not remove duplicate entries, use $HISTCONTROL for managing such entries.
        """

        if source == target:
            raise self.Error("source and target backend can't be the same")

        src = construct_history(backend=source, filename=source_file, gc=False)
        dest = construct_history(backend=target, filename=target_file, gc=False)

        for entry in src.all_items():
            dest.append(entry)

        dest.flush()

        self.out("Done")

    def build(self):
        parser = self.create_parser(prog="history")
        parser.add_command(self.show, prefix_chars="-+")
        parser.add_command(self.id_cmd, prog="id")
        parser.add_command(self.file)
        parser.add_command(self.info)
        parser.add_command(self.pull)
        parser.add_command(self.flush)
        parser.add_command(self.off)
        parser.add_command(self.on)
        parser.add_command(self.clear)
        parser.add_command(self.delete)
        parser.add_command(self.gc)
        parser.add_command(self.transfer)

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


history_main = HistoryAlias(threadable=True)
