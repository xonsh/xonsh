# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import collections
from xonsh.history.base import HistoryBase


class DummyHistory(HistoryBase):
    """A dummy implement of history backend."""
    def append(self, cmd):
        pass

    def items(self):
        yield {'inp': 'dummy in action', 'ts': 1464652800, 'ind': 0}

    def session_items(self):
        return self.items()

    def info(self):
        data = collections.OrderedDict()
        data['backend'] = 'dummy'
        data['sessionid'] = str(self.sessionid)
        return data
