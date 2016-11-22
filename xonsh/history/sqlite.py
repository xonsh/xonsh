# -*- coding: utf-8 -*-
"""Implements the xonsh history backend via sqlite3."""
import threading
import time


class HistoryGC(threading.Thread):
    pass


class History:
    def __init__(self, gc=True, **kwargs):
        self.gc = HistoryGC() if gc else None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

    def append(self, cmd):
        print('SqliteHistory append cmd: {}'.format(cmd))

    def flush(self, at_exit=False):
        print('SqliteHistory flush() called')

    def get_history_items(self):
        return [{'inp': 'sqlite3 in action\n'}]
