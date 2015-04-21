"""Implements the xonsh history object"""

from collections import OrderedDict
import json
import time

class History(object):

    ordered_history = OrderedDict()

    def load_history(self, hist_file="~/.xonsh_history.json"):
        try: 
            with open(hist_file) as data_file:
                json_history = json.load(data_file)
            print(str(json_history))
        except:
            print("No previous history")


    def add(self, cmd):
        self.ordered_history[time.time()] = {'cmd': cmd.strip()}
