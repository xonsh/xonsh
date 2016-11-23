# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import threading

from xonsh.history.base import HistoryBase


class DummyHistory(HistoryBase):
    def append(self, cmd):
        print('DummyHistory append: {}'.format(cmd))

    def flush(self, at_exit=False):
        print('DummyHistory flush ...')

    def items(self):
        for item in [{'inp': 'dummy in action\n'}]:
            yield item
