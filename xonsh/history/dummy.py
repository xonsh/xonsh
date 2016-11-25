# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import collections
import json

from xonsh.history.base import HistoryBase


class DummyHistory(HistoryBase):
    def append(self, cmd):
        pass

    def flush(self, at_exit=False):
        pass

    def items(self):
        """Display all history items."""
        yield {'inp': 'dummy in action', 'ts': 1464652800, 'ind': 0}

    def session_items(self):
        """Display history items of current session."""
        return self.items()

    def show_info(self, ns, stdout=None, stderr=None):
        """Display information about the shell history."""
        data = collections.OrderedDict()
        data['backend'] = 'dummy'
        data['sessionid'] = str(self.sessionid)
        if ns.json:
            s = json.dumps(data)
            print(s, file=stdout)
        else:
            for k, v in data.items():
                print('{}: {}'.format(k, v))
