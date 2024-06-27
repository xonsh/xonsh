"""Interfaces to locate executable files on file system."""

import os
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.platform import ON_WINDOWS


def get_possible_names(name, env=None):
    """Expand name to all possible variants based on `PATHEXT`.

    PATHEXT is a Windows convention containing extensions to be
    considered when searching for an executable file.

    Conserves order of any extensions found and gives precedence
    to the bare name.
    """
    env = env if env is not None else XSH.env
    env_pathext = env.get("PATHEXT", [])
    extensions = [""] + env_pathext
    return [name + ext for ext in extensions]


def clear_paths(paths):
    """Remove duplicates and nonexistent directories from paths."""
    cont = set()
    for p in map(os.path.realpath, paths):
        if p not in cont:
            cont.add(p)
            if os.path.isdir(p):
                yield p


def is_executable_in_windows(filepath, env=None):
    """Check the file is executable in Windows."""
    filepath = Path(filepath)
    try:
        try:
            if not filepath.is_file():
                return False
        except OSError:
            return False

        env = env if env is not None else XSH.env
        env_pathext = env.get("PATHEXT", [])
        if filepath.suffix.upper() in env_pathext:
            return True
    except FileNotFoundError:
        # On Windows, there's no guarantee for the directory to really
        # exist even if isdir returns True. This may happen for instance
        # if the path contains trailing spaces.
        return False


def is_executable_in_posix(filepath):
    """Check the file is executable in POSIX."""
    try:
        if filepath.is_file() and os.access(filepath, os.X_OK):
            return True
    except OSError:
        # broken Symlink are neither dir not files
        pass
    return False


def locate_executable(name, env=None):
    """Search executable binary name in $PATH and return full path."""
    env = env if env is not None else XSH.env
    env_path = env.get("PATH", [])
    paths = tuple(reversed(tuple(clear_paths(env_path))))
    possible_names = get_possible_names(name)
    for path in paths:
        for possible_name in possible_names:
            filepath = Path(path) / possible_name

            if ON_WINDOWS:
                is_executable = is_executable_in_windows
            else:
                is_executable = is_executable_in_posix

            try:
                if is_executable(filepath):
                    return str(filepath)
            except PermissionError:
                return
