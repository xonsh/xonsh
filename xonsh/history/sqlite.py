# -*- coding: utf-8 -*-
"""Implements the xonsh history backend via sqlite3."""
import builtins
import os.path
import sqlite3
import threading
import time

from xonsh.tools import expanduser_abs_path

__all__ = ['History']


def _get_conn():
    data_dir = builtins.__xonsh_env__.get('XONSH_DATA_DIR')
    data_dir = expanduser_abs_path(data_dir)
    db_file = os.path.join(data_dir, 'xonsh-history.db')
    return sqlite3.connect(db_file)


def _create_history_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xonsh_history
             (inp TEXT,
              rtn INTEGER,
              tsb REAL,
              tse REAL
             )
    """)


def _insert_command(cursor, cmd):
    cursor.execute("""
        INSERT INTO xonsh_history VALUES(?, ?, ?, ?)
    """, (cmd['inp'].rstrip(), cmd['rtn'], cmd['ts'][0], cmd['ts'][1]))


def _get_records(cursor):
    cursor.execute("""SELECT inp FROM xonsh_history ORDER BY tsb""")
    return cursor.fetchall()


def append_history(cmd):
    with _get_conn() as conn:
        c = conn.cursor()
        _create_history_table(c)
        _insert_command(c, cmd)
        conn.commit()


def get_history_items():
    with _get_conn() as conn:
        c = conn.cursor()
        _create_history_table(c)
        return _get_records(c)


class HistoryGC(threading.Thread):
    pass


class History:
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
        append_history(cmd)
        print('history cmd: {} took {:.4f}s'.format(cmd, time.time() - t))

    def flush(self, at_exit=False):
        print('SqliteHistory flush() called')

    def get_history_items(self):
        records = get_history_items()
        return [{'inp': x[0]} for x in records]
