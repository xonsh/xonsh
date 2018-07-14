# -*- coding: utf-8 -*-
"""History object for use with prompt_toolkit."""
import builtins
from threading import Thread

import prompt_toolkit.history


class PromptToolkitHistory(prompt_toolkit.history.History):
    """History class that implements the prompt-toolkit history interface
    with the xonsh backend.
    """

    def __init__(self, load_prev=True, wait_for_gc=True, *args, **kwargs):
        """Initialize history object."""
        super().__init__()
        #self.strings = []

    def store_string(self, entry):
        """Append new entry to the history."""
        self.strings.append(entry)

    def load_history_strings(self):
        """Loads synchronous history strings"""
        yield from self.load_history_strings_async()

    def load_history_strings_async(self):
        """Loads asynchronous history strings"""
        hist = builtins.__xonsh_history__
        if hist is None:
            return
        buf = None
        for cmd in hist.all_items():
            line = cmd['inp'].rstrip()
            strs = self.get_strings()
            if len(strs) == 0 or line != strs[-1]:
                yield line
                #if buf is None:
                #    buf = self._buf()
                #    if buf is None:
                #        continue
                #buf.reset(initial_document=buf.document)

    def _buf(self):
        # Thread-safe version of
        # buf = builtins.__xonsh_shell__.shell.prompter.cli.application.buffer
        path = ['__xonsh_shell__', 'shell', 'prompter', 'cli', 'application',
                'buffer']
        buf = builtins
        for a in path:
            buf = getattr(buf, a, None)
            if buf is None:
                break
        return buf

    def __getitem__(self, index):
        return self.get_strings()[index]

    def __len__(self):
        return len(self.get_strings())

    def __iter__(self):
        return iter(self.get_strings())
