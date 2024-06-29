"""Implements the xonsh history backend via sqlite3."""

import collections
import json
import os
import re
import sqlite3
import sys
import threading
import time

import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.history.base import History

XH_SQLITE_CACHE = threading.local()
XH_SQLITE_TABLE_NAME = "xonsh_history"
XH_SQLITE_CREATED_SQL_TBL = "CREATED_SQL_TABLE"


def _xh_sqlite_get_file_name():
    envs = XSH.env
    file_name = envs.get("XONSH_HISTORY_SQLITE_FILE")
    if not file_name:
        data_dir = envs.get("XONSH_DATA_DIR")
        file_name = os.path.join(data_dir, "xonsh-history.sqlite")
    return xt.expanduser_abs_path(file_name)


def _xh_sqlite_get_conn(filename=None):
    if filename is None:
        filename = _xh_sqlite_get_file_name()
    return sqlite3.connect(str(filename))


def _xh_sqlite_create_history_table(cursor):
    """Create Table for history items.

    Columns:
        info - JSON formatted, reserved for future extension.
        frequency - in case of HISTCONTROL=erasedups,
        it tracks the frequency of the inputs. helps in sorting autocompletion
    """
    if not getattr(XH_SQLITE_CACHE, XH_SQLITE_CREATED_SQL_TBL, False):
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {XH_SQLITE_TABLE_NAME}
                 (inp TEXT,
                  rtn INTEGER,
                  tsb REAL,
                  tse REAL,
                  sessionid TEXT,
                  out TEXT,
                  info TEXT,
                  frequency INTEGER default 1,
                  cwd TEXT
                 )
        """
        )

        # add frequency column if not exists for backward compatibility
        try:
            cursor.execute(
                "ALTER TABLE "
                + XH_SQLITE_TABLE_NAME
                + " ADD COLUMN frequency INTEGER default 1"
            )
        except sqlite3.OperationalError:
            pass

        # add path column if not exists for backward compatibility
        try:
            cursor.execute(
                "ALTER TABLE " + XH_SQLITE_TABLE_NAME + " ADD COLUMN cwd TEXT"
            )
        except sqlite3.OperationalError:
            pass

        # add index on inp. since we query when erasedups is True
        cursor.execute(
            f"""\
CREATE INDEX IF NOT EXISTS  idx_inp_history
ON {XH_SQLITE_TABLE_NAME}(inp);"""
        )

        # mark that this function ran for this session
        setattr(XH_SQLITE_CACHE, XH_SQLITE_CREATED_SQL_TBL, True)


def _xh_sqlite_get_frequency(cursor, input):
    # type: (sqlite3.Cursor, str) -> int
    sql = f"SELECT sum(frequency) FROM {XH_SQLITE_TABLE_NAME} WHERE inp=?"
    cursor.execute(sql, (input,))
    return cursor.fetchone()[0] or 0


def _xh_sqlite_erase_dups(cursor, input):
    freq = _xh_sqlite_get_frequency(cursor, input)
    sql = f"DELETE FROM {XH_SQLITE_TABLE_NAME} WHERE inp=?"
    cursor.execute(sql, (input,))
    return freq


def _sql_insert(cursor, values):
    # type: (sqlite3.Cursor, dict) -> None
    """handy function to run insert query"""
    sql = "INSERT INTO {} ({}) VALUES ({});"
    fields = ", ".join(values)
    marks = ", ".join(["?"] * len(values))
    cursor.execute(
        sql.format(XH_SQLITE_TABLE_NAME, fields, marks), tuple(values.values())
    )


def _xh_sqlite_insert_command(cursor, cmd, sessionid, store_stdout, remove_duplicates):
    tss = cmd.get("ts", [None, None])
    values = collections.OrderedDict(
        [
            ("inp", cmd["inp"].rstrip()),
            ("rtn", cmd["rtn"]),
            ("tsb", tss[0]),
            ("tse", tss[1]),
            ("sessionid", sessionid),
        ]
    )
    if "cwd" in cmd:
        values["cwd"] = cmd["cwd"]
    if store_stdout and "out" in cmd:
        values["out"] = cmd["out"]
    if "info" in cmd:
        info = json.dumps(cmd["info"])
        values["info"] = info
    if remove_duplicates:
        values["frequency"] = _xh_sqlite_erase_dups(cursor, values["inp"]) + 1
    _sql_insert(cursor, values)


def _xh_sqlite_get_count(cursor, sessionid=None):
    sql = "SELECT count(*) FROM xonsh_history "
    params = []
    if sessionid is not None:
        sql += "WHERE sessionid = ? "
        params.append(str(sessionid))
    cursor.execute(sql, tuple(params))
    return cursor.fetchone()[0]


def _xh_sqlite_get_records(cursor, sessionid=None, limit=None, newest_first=False):
    sql = "SELECT inp, tsb, rtn, frequency, cwd FROM xonsh_history "
    params = []
    if sessionid is not None:
        sql += "WHERE sessionid = ? "
        params.append(sessionid)
    sql += "ORDER BY tsb "
    if newest_first:
        sql += "DESC "
    if limit is not None:
        sql += "LIMIT %d " % limit
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()


def _xh_sqlite_delete_records(cursor, size_to_keep):
    sql = "SELECT min(tsb) FROM ("
    sql += "SELECT tsb FROM xonsh_history ORDER BY tsb DESC "
    sql += "LIMIT %d)" % size_to_keep
    cursor.execute(sql)
    result = cursor.fetchone()
    if not result:
        return
    max_tsb = result[0]
    sql = "DELETE FROM xonsh_history WHERE tsb < ?"
    result = cursor.execute(sql, (max_tsb,))
    return result.rowcount


def xh_sqlite_append_history(
    cmd, sessionid, store_stdout, filename=None, remove_duplicates=False
):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        _xh_sqlite_insert_command(c, cmd, sessionid, store_stdout, remove_duplicates)
        conn.commit()


def xh_sqlite_get_count(sessionid=None, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        return _xh_sqlite_get_count(c, sessionid=sessionid)


def xh_sqlite_items(sessionid=None, filename=None, newest_first=False):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_get_records(c, sessionid=sessionid, newest_first=newest_first)


def xh_sqlite_delete_items(size_to_keep, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_delete_records(c, size_to_keep)


def xh_sqlite_pull(filename, last_pull_time, current_sessionid):
    sql = "SELECT inp FROM xonsh_history WHERE tsb > ? AND sessionid != ? ORDER BY tsb"
    params = [last_pull_time, current_sessionid]
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        c.execute(sql, tuple(params))
        return c.fetchall()


def xh_sqlite_wipe_session(sessionid=None, filename=None):
    """Wipe the current session's entries from the database."""
    sql = "DELETE FROM xonsh_history WHERE sessionid = ?"
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        c.execute(sql, (str(sessionid),))


def xh_sqlite_delete_input_matching(pattern, filename=None):
    """Deletes entries from the database where the input matches a pattern."""
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        for inp, *_ in _xh_sqlite_get_records(c):
            if pattern.match(inp):
                sql = f"DELETE FROM xonsh_history WHERE inp = '{inp}'"
                c.execute(sql)


class SqliteHistoryGC(threading.Thread):
    """Shell history garbage collection."""

    def __init__(self, wait_for_shell=True, size=None, filename=None, *args, **kwargs):
        """Thread responsible for garbage collecting old history.

        May wait for shell (and for xonshrc to have been loaded) to start work.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.filename = filename
        self.size = size
        self.wait_for_shell = wait_for_shell
        self.start()

    def run(self):
        while self.wait_for_shell:
            time.sleep(0.01)
        if self.size is not None:
            hsize, units = xt.to_history_tuple(self.size)
        else:
            envs = XSH.env
            hsize, units = envs.get("XONSH_HISTORY_SIZE")
        if units != "commands":
            print(
                "sqlite backed history gc currently only supports "
                '"commands" as units',
                file=sys.stderr,
            )
            return
        if hsize < 0:
            return
        xh_sqlite_delete_items(hsize, filename=self.filename)


class SqliteHistory(History):
    """Xonsh history backend implemented with sqlite3."""

    def __init__(self, gc=True, filename=None, save_cwd=None, **kwargs):
        super().__init__(**kwargs)
        if filename is None:
            filename = _xh_sqlite_get_file_name()
        self.filename = filename
        self.last_pull_time = time.time()
        self.gc = SqliteHistoryGC() if gc else None
        self._last_hist_inp = None
        self.inps = []
        self.rtns = []
        self.outs = []
        self.tss = []
        self.cwds = []
        self.save_cwd = (
            save_cwd
            if save_cwd is not None
            else XSH.env.get("XONSH_HISTORY_SAVE_CWD", True)
        )

        if not os.path.exists(self.filename):
            with _xh_sqlite_get_conn(filename=self.filename) as conn:
                if conn:
                    pass
            try:
                os.chmod(self.filename, 0o600)
            except Exception:  # pylint: disable=broad-except
                pass

        # during init rerun create command
        setattr(XH_SQLITE_CACHE, XH_SQLITE_CREATED_SQL_TBL, False)

    def append(self, cmd):
        if (not self.remember_history) or self.is_ignored(cmd):
            return
        envs = XSH.env
        inp = cmd["inp"].rstrip()
        self.inps.append(inp)
        self.outs.append(cmd.get("out"))
        self.rtns.append(cmd["rtn"])
        self.tss.append(cmd.get("ts", (None, None)))
        self.cwds.append(cmd.get("cwd", None))

        opts = envs.get("HISTCONTROL", "")
        if "ignoredups" in opts and inp == self._last_hist_inp:
            # Skipping dup cmd
            return
        if "ignoreerr" in opts and cmd["rtn"] != 0:
            # Skipping failed cmd
            return
        if "ignorespace" in opts and cmd.get("spc"):
            # Skipping cmd starting with space
            return
        if not self.save_cwd and "cwd" in cmd:
            del cmd["cwd"]

        try:
            del cmd["spc"]
        except KeyError:
            pass
        self._last_hist_inp = inp
        try:
            xh_sqlite_append_history(
                cmd,
                str(self.sessionid),
                store_stdout=envs.get("XONSH_STORE_STDOUT", False),
                filename=self.filename,
                remove_duplicates=("erasedups" in opts),
            )
        except sqlite3.OperationalError as err:
            print(f"SQLite History Backend Error: {err}")

    def all_items(self, newest_first=False, session_id=None):
        """Display all history items."""
        for inp, ts, rtn, freq, cwd in xh_sqlite_items(
            filename=self.filename, newest_first=newest_first, sessionid=session_id
        ):
            yield {"inp": inp, "ts": ts, "rtn": rtn, "frequency": freq, "cwd": cwd}

    def items(self, newest_first=False):
        """Display history items of current session."""
        yield from self.all_items(newest_first, session_id=str(self.sessionid))

    def info(self):
        data = collections.OrderedDict()
        data["backend"] = "sqlite"
        data["sessionid"] = str(self.sessionid)
        data["filename"] = self.filename
        data["session items"] = xh_sqlite_get_count(
            sessionid=self.sessionid, filename=self.filename
        )
        data["all items"] = xh_sqlite_get_count(filename=self.filename)
        envs = XSH.env
        data["gc options"] = envs.get("XONSH_HISTORY_SIZE")
        return data

    def pull(self, show_commands=False):
        if not hasattr(XSH.shell.shell, "prompter"):
            print(f"Shell type {XSH.shell.shell} is not supported.")
            return 0

        cnt = 0
        for r in xh_sqlite_pull(
            self.filename, self.last_pull_time, str(self.sessionid)
        ):
            if show_commands:
                print(r[0])
            XSH.shell.shell.prompter.history.append_string(r[0])
            cnt += 1
        self.last_pull_time = time.time()
        return cnt

    def run_gc(self, size=None, blocking=True, **_):
        self.gc = SqliteHistoryGC(wait_for_shell=False, size=size)
        if blocking:
            while self.gc.is_alive():
                continue

    def clear(self):
        """Clears the current session's history from both memory and disk."""
        # Wipe memory
        self.inps = []
        self.rtns = []
        self.outs = []
        self.tss = []
        self.cwds = []

        xh_sqlite_wipe_session(sessionid=self.sessionid, filename=self.filename)

    def delete(self, pattern):
        """Deletes all entries in the database where the input matches a pattern."""
        xh_sqlite_delete_input_matching(
            pattern=re.compile(pattern), filename=self.filename
        )
