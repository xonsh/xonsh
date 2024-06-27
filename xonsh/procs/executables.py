"""Interfaces to locate executable files on file system."""

import os
from pathlib import Path
from xonsh.built_ins import XSH
from xonsh.commands_cache import CommandsCache

def locate_executable(filename):
    """Search executable binary filename in $PATH and return full path."""
    paths = tuple(reversed(tuple(CommandsCache.remove_dups(XSH.env.get("PATH") or []))))
    for path in paths:
        filepath = (Path(path) / filename)
        if filepath.is_file() and os.access(filepath, os.X_OK):
            return str(filepath)


#possibilities = self.get_possible_names(name)