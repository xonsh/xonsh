# -*- coding: utf-8 -*-
"""History object for use with prompt_toolkit."""
import time
import builtins
from threading import Thread

import prompt_toolkit.history
from xonsh import lazyjson


class PromptToolkitHistory(prompt_toolkit.history.History):
    """History class that implements the promt-toolkit history interface
    with the xonsh backend.
    """

    def __init__(self, load_prev=True, wait_for_gc=True, *args, **kwargs):
        """Initialize history object."""
        super().__init__()
        self.strings = []
        if load_prev:
            PromptToolkitHistoryAdder(self, wait_for_gc=wait_for_gc)

    def append(self, entry):
        """Append new entry to the history."""
        self.strings.append(entry)

    def __getitem__(self, index):
        return self.strings[index]

    def __len__(self):
        return len(self.strings)

    def __iter__(self):
        return iter(self.strings)


class PromptToolkitHistoryAdder(Thread):

    def __init__(self, ptkhist, wait_for_gc=True, *args, **kwargs):
        """Thread responsible for adding inputs from history to the current 
        prompt-toolkit history instance. May wait for the history garbage 
        collector to finish.
        """
        super(PromptToolkitHistoryAdder, self).__init__(*args, **kwargs)
        self.daemon = True
        self.ptkhist = ptkhist
        self.wait_for_gc = wait_for_gc
        self.start()

    def run(self):
        hist = builtins.__xonsh_history__
        buf = None
        ptkhist = self.ptkhist
        while self.wait_for_gc and hist.gc.is_alive():
            time.sleep(0.011)  # gc sleeps for 0.01 secs, sleep a beat longer
        files = hist.gc.unlocked_files()
        for _, _, f in files:
            try:
                lj = lazyjson.LazyJSON(f, reopen=False)
                for cmd in lj['cmds']:
                    line = cmd['inp'].rstrip()
                    if line == 'EOF':
                        continue
                    if len(ptkhist) == 0 or line != ptkhist[-1]:
                        ptkhist.append(line)
                        if buf is None:
                            buf = self._buf()
                            if buf is None:
                                continue
                        buf.reset(initial_document=buf.document)
                lj.close()
            except (IOError, OSError):
                continue

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
        
