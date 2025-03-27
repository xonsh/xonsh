"""Interfaces to locate executable files on file system."""

import itertools
import os
from pathlib import Path

from xonsh.built_ins import XSH
from xonsh.lib.itertools import unique_everseen
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
    return filter(os.path.isdir, unique_everseen(map(os.path.realpath, paths)))


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
        return any(s.lower() == filepath.suffix.lower() for s in env.get("PATHEXT", []))
    except FileNotFoundError:
        # On Windows, there's no guarantee for the directory to really
        # exist even if isdir returns True. This may happen for instance
        # if the path contains trailing spaces.
        return False


def is_executable_in_posix(filepath):
    """Check the file is executable in POSIX."""
    try:
        return filepath.is_file() and os.access(filepath, os.X_OK)
    except OSError:
        # broken Symlink are neither dir not files
        pass
    return False


is_executable = is_executable_in_windows if ON_WINDOWS else is_executable_in_posix


def locate_executable(name, env=None):
    """Search executable binary name in ``$PATH`` and return full path."""
    return locate_file(name, env=env, check_executable=True, use_pathext=True)


def locate_file(name, env=None, check_executable=False, use_pathext=False):
    """Search file name in the current working directory and in ``$PATH`` and return full path."""
    return locate_relative_path(
        name, env, check_executable, use_pathext
    ) or locate_file_in_path_env(name, env, check_executable, use_pathext)


def locate_relative_path(name, env=None, check_executable=False, use_pathext=False):
    """Return absolute path by relative file path.

    We should not locate files without prefix (e.g. ``"binfile"``) by security reasons like other shells.
    If directory has "binfile" it can be called only by providing prefix "./binfile" explicitly.
    """
    p = Path(name)
    if name.startswith(("./", "../", ".\\", "..\\", "~/")) or p.is_absolute():
        possible_names = get_possible_names(p.name, env) if use_pathext else [p.name]
        for possible_name in possible_names:
            filepath = p.parent / possible_name
            try:
                if not filepath.is_file() or (
                    check_executable and not is_executable(filepath)
                ):
                    continue
                return str(p.absolute())
            except PermissionError:
                continue


from os import walk


def check_possible_name(path, possible_name, check_executable):
    filepath = Path(path) / possible_name
    try:
        if not filepath.is_file() or (check_executable and not is_executable(filepath)):
            return
        return str(filepath)
    except PermissionError:
        return


def locate_file_in_path_env(name, env=None, check_executable=False, use_pathext=False):
    """Search file name in ``$PATH`` and return full path.

    Compromise. There is no way to get case sensitive file name without listing all files.
    If the file name is ``CaMeL.exe`` and we found that ``camel.EXE`` exists there is no way
    to get back the case sensitive name. We don't want to read the list of files in all ``$PATH``
    directories because of performance reasons. So we're ok to get existent
    but case insensitive (or different) result from resolver.
    May be in the future file systems as well as Python Path will be smarter to get the case sensitive name.
    The task for reading and returning case sensitive filename we give to completer in interactive mode
    with ``commands_cache``.

    Typing speed boost: on Windows instead of checking that 10+ file.pathext files exist it's faster
    to scan a smaller dir and check whether those 10+ strings are in this list
    XONSH_DIR_CACHE_TO_LIST allows users to do just that
    """
    env = env if env is not None else XSH.env
    env_path = env.get("PATH", [])
    paths = tuple(clear_paths(env_path))
    path_to_list = env.get("XONSH_DIR_CACHE_TO_LIST", [])
    possible_names = get_possible_names(name, env) if use_pathext else [name]

    if path_to_list and (len(possible_names) > 2):
        for path in paths:
            if path in path_to_list:
                f = []
                for _dirpath, _dirnames, filenames in walk(path):
                    f.extend(filenames)
                    break  # no recursion into subdir
                for possible_name in possible_names:
                    if possible_name not in f:
                        continue
                    if found := check_possible_name(
                        path, possible_name, check_executable
                    ):
                        return found
                    else:
                        continue
            else:
                for possible_name in possible_names:
                    if found := check_possible_name(
                        path, possible_name, check_executable
                    ):
                        return found
                    else:
                        continue
    else:
        for path, possible_name in itertools.product(paths, possible_names):
            if found := check_possible_name(path, possible_name, check_executable):
                return found
            else:
                continue
