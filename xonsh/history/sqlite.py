# -*- coding: utf-8 -*-
"""Implements the xonsh history backend via sqlite3."""
import builtins
import collections
import json
import os
import sqlite3
import sys
import threading
import time

from xonsh.history.base import History
import xonsh.tools as xt


def _xh_sqlite_get_file_name():
    envs = builtins.__xonsh_env__
    file_name = envs.get('XONSH_HISTORY_SQLITE_FILE')
    if not file_name:
        data_dir = envs.get('XONSH_DATA_DIR')
        file_name = os.path.join(data_dir, 'xonsh-history.sqlite')
    return xt.expanduser_abs_path(file_name)


def _xh_sqlite_get_conn(filename=None):
    if filename is None:
        filename = _xh_sqlite_get_file_name()
    return sqlite3.connect(filename)


def _xh_sqlite_create_history_table(cursor):
    """Create Table for history items.

    Columns:
        info - JSON formated, reserved for future extension.
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xonsh_history
             (inp TEXT,
              rtn INTEGER,
              tsb REAL,
              tse REAL,
              sessionid TEXT,
              out TEXT,
              info TEXT
             )
    """)


def _xh_sqlite_insert_command(cursor, cmd, sessionid, store_stdout):
    sql = 'INSERT INTO xonsh_history (inp, rtn, tsb, tse, sessionid'
    tss = cmd.get('ts', [None, None])
    params = [
        cmd['inp'].rstrip(),
        cmd['rtn'],
        tss[0],
        tss[1],
        sessionid,
    ]
    if store_stdout and 'out' in cmd:
        sql += ', out'
        params.append(cmd['out'])
    if 'info' in cmd:
        sql += ', info'
        info = json.dumps(cmd['info'])
        params.append(info)
    sql += ') VALUES (' + ('?, ' * len(params)).rstrip(', ') + ')'
    cursor.execute(sql, tuple(params))


def _xh_sqlite_get_count(cursor, sessionid=None):
    sql = 'SELECT count(*) FROM xonsh_history '
    params = []
    if sessionid is not None:
        sql += 'WHERE sessionid = ? '
        params.append(str(sessionid))
    cursor.execute(sql, tuple(params))
    return cursor.fetchone()[0]


def _xh_sqlite_get_records(cursor, sessionid=None, limit=None, reverse=False):
    sql = 'SELECT inp, tsb, rtn FROM xonsh_history '
    params = []
    if sessionid is not None:
        sql += 'WHERE sessionid = ? '
        params.append(sessionid)
    sql += 'ORDER BY tsb '
    if reverse:
        sql += 'DESC '
    if limit is not None:
        sql += 'LIMIT %d ' % limit
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()


def _xh_sqlite_delete_records(cursor, size_to_keep):
    sql = 'SELECT min(tsb) FROM ('
    sql += 'SELECT tsb FROM xonsh_history ORDER BY tsb DESC '
    sql += 'LIMIT %d)' % size_to_keep
    cursor.execute(sql)
    result = cursor.fetchone()
    if not result:
        return
    max_tsb = result[0]
    sql = 'DELETE FROM xonsh_history WHERE tsb < ?'
    result = cursor.execute(sql, (max_tsb,))
    return result.rowcount


def xh_sqlite_append_history(cmd, sessionid, store_stdout, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        _xh_sqlite_insert_command(c, cmd, sessionid, store_stdout)
        conn.commit()


def xh_sqlite_get_count(sessionid=None, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        return _xh_sqlite_get_count(c, sessionid=sessionid)


def xh_sqlite_items(sessionid=None, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_get_records(c, sessionid=sessionid)


def xh_sqlite_delete_items(size_to_keep, filename=None):
    with _xh_sqlite_get_conn(filename=filename) as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_delete_records(c, size_to_keep)


class SqliteHistoryGC(threading.Thread):
    """Shell history garbage collection."""

    def __init__(self, wait_for_shell=True, size=None, filename=None,
                 *args, **kwargs):
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
            envs = builtins.__xonsh_env__
            hsize, units = envs.get('XONSH_HISTORY_SIZE')
        if units != 'commands':
            print('sqlite backed history gc currently only supports '
                  '"commands" as units', file=sys.stderr)
            return
        if hsize < 0:
            return
        xh_sqlite_delete_items(hsize, filename=self.filename)


class SqliteHistory(History):
    """Xonsh history backend implemented with sqlite3."""

    def __init__(self, gc=True, filename=None, **kwargs):
        super().__init__(**kwargs)
        if filename is None:
            filename = _xh_sqlite_get_file_name()
        self.filename = filename
        self.gc = SqliteHistoryGC() if gc else None
        self._last_hist_inp = None
        self.inps = []
        self.rtns = []
        self.outs = []
        self.tss = []

    def append(self, cmd):
        envs = builtins.__xonsh_env__
        opts = envs.get('HISTCONTROL')
        inp = cmd['inp'].rstrip()
        self.inps.append(inp)
        store_stdout = envs.get('XONSH_STORE_STDOUT', False)
        if store_stdout:
            self.outs.append(cmd.get('out'))
        else:
            self.outs.append(None)
        self.rtns.append(cmd['rtn'])
        self.tss.append(cmd.get('ts', (None, None)))

        opts = envs.get('HISTCONTROL')
        if 'ignoredups' in opts and inp == self._last_hist_inp:
            # Skipping dup cmd
            return
        if 'ignoreerr' in opts and cmd['rtn'] != 0:
            # Skipping failed cmd
            return
        self._last_hist_inp = inp
        xh_sqlite_append_history(
            cmd, str(self.sessionid), store_stdout,
            filename=self.filename)

    def all_items(self):
        """Display all history items."""
        for item in xh_sqlite_items(filename=self.filename):
            yield {'inp': item[0], 'ts': item[1], 'rtn': item[2]}

    def items(self):
        """Display history items of current session."""
        for item in xh_sqlite_items(
                sessionid=str(self.sessionid), filename=self.filename):
            yield {'inp': item[0], 'ts': item[1], 'rtn': item[2]}

    def info(self):
        data = collections.OrderedDict()
        data['backend'] = 'sqlite'
        data['sessionid'] = str(self.sessionid)
        data['filename'] = self.filename
        data['session items'] = xh_sqlite_get_count(
            sessionid=self.sessionid, filename=self.filename)
        data['all items'] = xh_sqlite_get_count(filename=self.filename)
        envs = builtins.__xonsh_env__
        data['gc options'] = envs.get('XONSH_HISTORY_SIZE')
        return data

    def run_gc(self, size=None, blocking=True):
        self.gc = SqliteHistoryGC(wait_for_shell=False, size=size)
        if blocking:
            while self.gc.is_alive():
                continue
