"""History object for use with prompt_toolkit."""
import os

from prompt_toolkit.history import History


def load_file_into_list(store, filename):
    """Load content of file filename into list store."""
    if os.path.exists(filename):
        with open(filename, 'rb') as hfile:
            for line in hfile:
                line = line.decode('utf-8')
                # Drop trailing newline
                store.append(line[:-1])


class LimitedFileHistory(History):

    """History class that keeps entries in file with limit on number of those.

    It handles only one-line entries.
    """

    def __init__(self):
        """Initialize history object."""
        self.strings = []
        self.new_entries = []
        self.old_history = []

    def append(self, entry):
        """Append new entry to the history.

        Entry sould be a one-liner.
        """
        self.strings.append(entry)
        self.new_entries.append(entry)

    def __getitem__(self, index):
        return self.strings[index]

    def __len__(self):
        return len(self.strings)

    def __iter__(self):
        return iter(self.strings)

    def read_history_file(self, filename):
        """Read history from given file into memory.

        It first discards all history entries that were read by this function
        before, and then tries to read entries from filename as history of
        commands that happend before current session.
        Entries that were appendend in current session are left unharmed.

        Parameters
        ----------
        filename : str
            Path to history file.
        """
        self.old_history = []
        load_file_into_list(self.old_history, filename)
        self.strings = self.old_history[:]
        self.strings.extend(self.new_entries)

    def save_history_to_file(self, filename, limit=-1):
        """Save history to file.

        It first reads existing history file again, so nothing is overrided. If
        combined number of entries from history file and current session
        exceeds limit old entries are dropped.
        Not thread safe.

        Parameters
        ----------
        filename : str
            Path to file to save history to.
        limit : int
            Limit on number of entries in history file. Negative values imply
            unlimited history.
        """
        def write_list(lst, file_obj):
            """Write each element of list as separate lint into file_obj."""
            text = ('\n'.join(lst)) + '\n'
            file_obj.write(text.encode('utf-8'))

        if limit < 0:
            with open(filename, 'ab') as hfile:
                write_list(self.new_entries, hfile)
            return

        new_history = []
        load_file_into_list(new_history, filename)

        if len(new_history) + len(self.new_entries) <= limit:
            if self.new_entries:
                with open(filename, 'ab') as hfile:
                    write_list(self.new_entries, hfile)
        else:
            new_history.extend(self.new_entries)
            with open(filename, 'wb') as hfile:
                write_list(new_history[-limit:], hfile)
