# -*- coding: utf-8 -*-
"""History object for use with prompt_toolkit."""
import builtins

import prompt_toolkit.history


class PromptToolkitHistory(prompt_toolkit.history.History):
    """History class that implements the prompt-toolkit history interface
    with the xonsh backend.
    """

    def __init__(self, load_prev=True, *args, **kwargs):
        """Initialize history object."""
        super().__init__()
        self.load_prev = load_prev

    def store_string(self, entry):
        pass

    def load_history_strings(self):
        """Loads synchronous history strings"""
        if not self.load_prev:
            return
        hist = builtins.__xonsh_history__
        if hist is None:
            return
        for cmd in hist.all_items():
            line = cmd['inp'].rstrip()
            strs = self.get_strings()
            if len(strs) == 0 or line != strs[-1]:
                yield line

    def __getitem__(self, index):
        return self.get_strings()[index]

    def __len__(self):
        return len(self.get_strings())

    def __iter__(self):
        return iter(self.get_strings())
