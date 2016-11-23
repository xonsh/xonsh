# -*- coding: utf-8 -*-
"""Implements the xonsh history backend via sqlite3."""
import builtins
import os
import sqlite3
import threading
import time

import xonsh.tools as xt


def _xh_sqlite_get_conn():
    data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
    data_dir = xt.expanduser_abs_path(data_dir)
    db_file = os.path.join(data_dir, 'xonsh-history.sqlite')
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
    cursor.execute('SELECT inp FROM xonsh_history ORDER BY tsb')
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


class HistoryGC(threading.Thread):
    pass


class SqliteHistory:
    def __init__(self, gc=True, **kwargs):
        self.gc = HistoryGC() if gc else None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None
        self.last_cmd_inp = None

    def __iter__(self):
        for cmd, ts, index in []:
            yield (cmd, ts, index)

    def append(self, cmd):
        opts = builtins.__xonsh_env__.get('HISTCONTROL')
        if 'ignoredups' in opts and cmd['inp'].rstrip() == self.last_cmd_inp:
            # Skipping dup cmd
            return
        if 'ignoreerr' in opts and cmd['rtn'] != 0:
            # Skipping failed cmd
            return
        self.last_cmd_inp = cmd['inp'].rstrip()
        t = time.time()
        xh_sqlite_append_history(cmd)
        print('history cmd: {} took {:.4f}s'.format(cmd, time.time() - t))

    def flush(self, at_exit=False):
        print('SqliteHistory flush() called')

    def items(self):
        records = xh_sqlite_items()
        return [{'inp': x[0]} for x in records]
