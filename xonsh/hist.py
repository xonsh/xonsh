"""Implements the xonsh history object"""

from collections import OrderedDict
import json
import time
import os


class History(object):

    ordered_history = OrderedDict()

    def load_history(self, hist_file="~/.xonsh_history.json"):
        """Loads previous history from ~/.xonsh_history.json if it exists.

        Parameters
        ----------
        hist_file : str, optional
            Path of the history file.

        Returns
        -------
            None
        """
        if os.path.isfile(hist_file):
            with open(hist_file) as data_file:
                json_history = json.load(data_file)


    def add(self, cmd):
        """Adds command with current timestamp to ordered history.

        Parameters
        ----------
        cmd: str
            Command that should be added to the ordered history.

        Returns
        -------
            None
        """
        self.ordered_history[time.time()] = {'cmd': cmd}
