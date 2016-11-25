# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import sys
from xonsh.history.base import HistoryBase


class DummyHistory(HistoryBase):
    def append(self, cmd):
        print('DummyHistory append: {}'.format(cmd), file=sys.stderr)

    def flush(self, at_exit=False):
        print('DummyHistory flush ...', file=sys.stderr)

    def items(self):
        yield {'inp': 'dummy in action\n'}
