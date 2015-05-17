"""History object for use with prompt_toolkit."""
import os

from prompt_toolkit.history import History


class LimitedFileHistory(History):
    """History class that keeps entries in file with limit on number of those.

    It handles only one-line entries.
    """

    def __init__(self):
        """Initializes history object."""
        super().__init__()
        self.new_entries = []
        self.old_history = []

    def append(self, entry):
        """Appends new entry to the history.

        Entry sould be a one-liner.
        """
        super().append(entry)
        self.new_entries.append(entry)

    def read_history_file(self, filename):
        """Reads history from given file into memory.

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
        self._load(self.old_history, filename)
        self.strings = self.old_history[:]
        self.strings.extend(self.new_entries)


    def save_history_to_file(self, filename, limit=-1):
        """Saves history to file.

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
        def write_list(lst, file):
            text = ('\n'.join(lst)) + '\n'
            file.write(text.encode('utf-8'))

        if limit < 0:
            with open(filename, 'ab') as hf:
                write_list(new_entries, hf)
            return

        new_history = []
        self._load(new_history, filename)

        if len(new_history) + len(self.new_entries) <= limit:
            with open(filename, 'ab') as hf:
                write_list(self.new_entries, hf)
        else:
            new_history.extend(self.new_entries)
            with open(filename, 'wb') as hf:
                write_list(new_history[-limit:], hf)

    def _load(self, store, filename):
        """Loads content of file filename into list store."""
        if os.path.exists(filename):
            with open(filename, 'rb') as hf:
                for line in hf:
                    line = line.decode('utf-8')
                    # Drop trailing newline
                    store.append(line[:-1])
