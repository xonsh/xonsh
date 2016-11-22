# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import threading

__all__ = ['History']


class HistoryGC(threading.Thread):
    pass


class History:
    def __init__(self, gc=True, **kwargs):
        self.gc = HistoryGC() if gc else None
        self.rtns = None
        self.last_cmd_rtn = None
        self.last_cmd_out = None

    def __iter__(self):
        for cmd, ts, index in []:
            yield (cmd, ts, index)

    def append(self, cmd):
        print('DummyHistory append cmd: {}'.format(cmd))

    def flush(self, at_exit=False):
        print('DummyHistory flush ...')

    def get_history_items(self):
        return [{'inp': 'dummy in action\n'}]
