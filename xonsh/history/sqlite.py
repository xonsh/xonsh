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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xonsh_history
             (inp TEXT,
              rtn INTEGER,
              tsb REAL,
              tse REAL
             )
    """)


def _xh_sqlite_insert_command(cursor, cmd):
    cursor.execute("""
        INSERT INTO xonsh_history VALUES(?, ?, ?, ?)
    """, (cmd['inp'].rstrip(), cmd['rtn'], cmd['ts'][0], cmd['ts'][1]))


def _xh_sqlite_get_records(cursor):
    cursor.execute('SELECT inp, tsb FROM xonsh_history ORDER BY tsb')
    return cursor.fetchall()


def xh_sqlite_append_history(cmd):
    with _xh_sqlite_get_conn() as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        _xh_sqlite_insert_command(c, cmd)
        conn.commit()


def xh_sqlite_items():
    with _xh_sqlite_get_conn() as conn:
        c = conn.cursor()
        _xh_sqlite_create_history_table(c)
        return _xh_sqlite_get_records(c)


class SqliteHistory(HistoryBase):
    def __init__(self, filename=None, **kwargs):
        super().__init__(**kwargs)
        if filename is None:
            filename = _xh_sqlite_get_file_name()
        self.filename = filename
        self.last_cmd_inp = None

    def append(self, cmd):
        opts = builtins.__xonsh_env__.get('HISTCONTROL')
        if 'ignoredups' in opts and cmd['inp'].rstrip() == self.last_cmd_inp:
            # Skipping dup cmd
            return
        if 'ignoreerr' in opts and cmd['rtn'] != 0:
            # Skipping failed cmd
            return
        self.last_cmd_inp = cmd['inp'].rstrip()
        xh_sqlite_append_history(cmd)

    def flush(self, at_exit=False):
        print('TODO: SqliteHistory flush() called')

    def items(self):
        i = 0
        for item in xh_sqlite_items():
            yield {'inp': item[0], 'ts': item[1], 'ind': i}
            i += 1

    def session_items(self):
        """Display history items of current session."""
        return self.items()

    def show_info(self, ns, stdout=None, stderr=None):
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
