# -*- coding: utf-8 -*-
"""Implements the xonsh history backend via sqlite3."""
import builtins
import collections
import json
import os
import sqlite3

from xonsh.history.base import HistoryBase
import xonsh.tools as xt


def _xh_sqlite_get_file_name():
    envs = builtins.__xonsh_env__
    file_name = envs.get('XONSH_HISTORY_SQLITE_FILE')
    if not file_name:
        data_dir = envs.get('XONSH_DATA_DIR')
        file_name = os.path.join(data_dir, 'xonsh-history.sqlite')
    return xt.expanduser_abs_path(file_name)


def _xh_sqlite_get_conn():
    db_file = _xh_sqlite_get_file_name()
    return sqlite3.connect(db_file)


def _xh_sqlite_create_history_table(cursor):
    """Create Table for history items.

    Columns:
        info - JSON formated, reserved for now.
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
    params = [
        cmd['inp'].rstrip(),
        cmd['rtn'],
        cmd['ts'][0],
        cmd['ts'][1],
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


def _xh_sqlite_get_records(cursor, sessionid=None, limit=None, reverse=False):
    sql = 'SELECT inp, tsb FROM xonsh_history '
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


def xh_sqlite_append_history(cmd, sessionid, store_stdout):
    with _xh_sqlite_get_conn() as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        _xh_sqlite_insert_command(c, cmd, sessionid, store_stdout)
        conn.commit()


def xh_sqlite_items(sessionid=None):
    with _xh_sqlite_get_conn() as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_get_records(c, sessionid=sessionid)


class SqliteHistory(HistoryBase):
    def __init__(self, filename=None, **kwargs):
        super().__init__(**kwargs)
        if filename is None:
            filename = _xh_sqlite_get_file_name()
        self.filename = filename
        self.last_cmd_inp = None

    def append(self, cmd):
        envs = builtins.__xonsh_env__
        opts = envs.get('HISTCONTROL')
        if 'ignoredups' in opts and cmd['inp'].rstrip() == self.last_cmd_inp:
            # Skipping dup cmd
            return
        if 'ignoreerr' in opts and cmd['rtn'] != 0:
            # Skipping failed cmd
            return
        store_stdout = envs.get('XONSH_STORE_STDOUT', False)
        self.last_cmd_inp = cmd['inp'].rstrip()
        xh_sqlite_append_history(cmd, str(self.sessionid), store_stdout)

    def items(self):
        """Display all history items."""
        i = 0
        for item in xh_sqlite_items():
            yield {'inp': item[0], 'ts': item[1], 'ind': i}
            i += 1

    def session_items(self):
        """Display history items of current session."""
        i = 0
        for item in xh_sqlite_items(sessionid=str(self.sessionid)):
            yield {'inp': item[0], 'ts': item[1], 'ind': i}
            i += 1

    def on_info(self, ns, stdout=None, stderr=None):
        """Display information about the shell history."""
        data = collections.OrderedDict()
        data['backend'] = 'sqlite'
        data['sessionid'] = str(self.sessionid)
        data['filename'] = self.filename
        if ns.json:
            s = json.dumps(data)
            print(s, file=stdout)
        else:
            for k, v in data.items():
                print('{}: {}'.format(k, v))
