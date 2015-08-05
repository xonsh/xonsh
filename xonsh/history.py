"""Implements the xonsh history object"""
import os
import sys
import json
import time
import uuid
import builtins
from collections import OrderedDict

from xonsh import lazyjson


class History(object):

    def __init__(self, filename=None, sessionid=None, buffersize=100):
        """Represents a xonsh session's history as an in-memory buffer that is
        periodically flushed to disk.

        Parameters
        ----------
        filename : str, optional
            
        """
        self.sessionid = uuid.uuid4() if sessionid is None else sessionid
        self.filename = '~/xonsh-{0}.json'.format(self.sessionid) \
            if filename is None else filename
        self.buffer = []
        self.buffersize = buffersize

    def open_history(self):
        """Loads previous history from ~/.xonsh_history.json or
        location specified in .xonshrc if it exists.
        """
        #if os.path.exists(self.hf):
        #    self.ordered_history = lazyjson.LazyJSON(self.hf).load()
        #else:
        #    sys.stdout.write("No history\n")


    def close_history(self):
        pass
        #with open(self.hf, 'w+') as fp:
        #    lazyjson.dump(self.ordered_history, fp) 


    def add(self, cmd):
        """Adds command with current timestamp to ordered history.

        Parameters
        ----------
        cmd: dict 
            Command dictionary that should be added to the ordered history.
        """
        #self.ordered_history[time.time()] = {'cmd': cmd}
        cmd['timestamp'] = time.time()
        #self.ordered_history.append(cmd)
