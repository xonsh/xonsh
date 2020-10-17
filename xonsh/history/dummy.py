# -*- coding: utf-8 -*-
"""Implements the xonsh history backend."""
import collections
import uuid

from xonsh.history.base import History


class DummyHistory(History):
    """A dummy implement of history backend."""

    def append(self, cmd):
        pass

    def items(self, newest_first=False):
        yield {"inp": "dummy in action", "ts": 1464652800, "ind": 0, "rtn": 0}

    def all_items(self, newest_first=False, full_item=False):
        if full_item:
            sessionid = self.sessionid or uuid.uuid4()
            for item in self.items(newest_first=newest_first):
                yield sessionid, item
        else:
            yield from self.items(newest_first=newest_first)

    def info(self):
        data = collections.OrderedDict()
        data["backend"] = "dummy"
        data["sessionid"] = str(self.sessionid)
        return data
