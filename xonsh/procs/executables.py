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
    if not env_pathext:
        return [name]
    upper = name.upper() == name
    extensions = [""] + env_pathext
    return [name + (ext.upper() if upper else ext.lower()) for ext in extensions]


def clear_paths(paths):
    """Remove duplicates and nonexistent directories from paths."""
    cont = set()
    for p in map(os.path.realpath, paths):
        if p not in cont:
            cont.add(p)
            if os.path.isdir(p):
                yield p


def get_paths(env=None):
    """Return tuple with deduplicated and existent paths from ``$PATH``."""
    env = env if env is not None else XSH.env
    return tuple(reversed(tuple(clear_paths(env.get("PATH") or []))))


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
    return locate_file(name, env=env, check_executable=True, use_pathext=True)


def locate_file(name, env=None, check_executable=False, use_pathext=False):
    """Search executable binary name in $PATH and return full path.

    Compromise. There is no way to get case sensitive file name without listing all files.
    If the file name is ``CaMeL.exe`` and we found that ``camel.EXE`` exists there is no way
    to get back the case sensitive name. Because we don't want to read the list of files
    in all ``$PATH`` directories because of performance reasons we're ok to get existent
    but case insensitive (or different) result from resolver.
    May be in the future file systems as well as Python Path will be smarter to get the case sensitive name.
    The task for reading and returning case sensitive filename we give to completer in interactive mode
    with ``commands_cache``.
    """
    env = env if env is not None else XSH.env
    env_path = env.get("PATH", [])
    paths = tuple(reversed(tuple(clear_paths(env_path))))
    possible_names = get_possible_names(name, env) if use_pathext else [name]

    if check_executable:
        if ON_WINDOWS:
            is_executable = is_executable_in_windows
        else:
            is_executable = is_executable_in_posix

    for path in paths:
        for possible_name in possible_names:
            filepath = Path(path) / possible_name

            try:
                if check_executable and not is_executable(filepath):
                    continue
                return str(filepath)
            except PermissionError:
                return
