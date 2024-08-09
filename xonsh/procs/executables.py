"""Interfaces to locate executable files on file system."""

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


def locate_executable(name, env=None, use_path_cache=True, use_dir_session_cache=False):
    """Search executable binary name in ``$PATH`` and return full path."""
    return locate_file(
        name,
        env=env,
        check_executable=True,
        use_pathext=True,
        use_path_cache=use_path_cache,
        use_dir_session_cache=use_dir_session_cache,
    )


class PathCache:
    is_dirty = True
    dir_cache: dict[str, list[list[str]]] = dict()
    clean_paths: dict[str, tuple[str]] = dict()

    @classmethod
    def get_clean(cls, env):
        if cls.is_dirty:
            env_path = env.get("PATH", [])
            env_path_hash = hash_s_list(env_path) # to test whether it matches PATH before
            # returning the cleaned version (avoid wrong cache for a env.swap(PATH=['a']))
            if not env_path_hash in cls.clean_paths:
                cls.clean_paths[env_path_hash] = tuple(clear_paths(env_path))
            cls.is_dirty = False
        return cls.clean_paths

    @classmethod
    def get_dir_cached(cls, path):
        return cls.dir_cache.get(path, [None, None])

    @classmethod
    def set_dir_cached(cls, path, File_list, file_list):
        cls.dir_cache[path] = [File_list, file_list]


def locate_file(
    name,
    env=None,
    check_executable=False,
    use_pathext=False,
    use_path_cache=True,
    use_dir_session_cache=False,
):
    """Search file name in the current working directory and in ``$PATH`` and return full path."""
    return locate_relative_path(
        name, env, check_executable, use_pathext
    ) or locate_file_in_path_env(
        name, env, check_executable, use_pathext, use_path_cache, use_dir_session_cache
    )


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

import hashlib
import struct
def hash_s_list(s_list):
    """
    Serialize a list of strings and hash them using sha256
    """
    hash_o = hashlib.sha256()
    for s in s_list: # Hash each string
        length_encoded = struct.pack("I",len(s))
        hash_o.update(length_encoded)
        hash_o.update(s.encode('utf-8'))
    return hash_o.hexdigest()

def locate_file_in_path_env(
    name,
    env=None,
    check_executable=False,
    use_pathext=False,
    use_path_cache=True,
    use_dir_session_cache=False,
):
    """Search file name in ``$PATH`` and return full path.

    Compromise. There is no way to get case sensitive file name without listing all files.
    If the file name is ``CaMeL.exe`` and we found that ``camel.EXE`` exists there is no way
    to get back the case sensitive name. We don't want to read the list of files in all ``$PATH``
    directories because of performance reasons. So we're ok to get existent
    but case insensitive (or different) result from resolver.
    May be in the future file systems as well as Python Path will be smarter to get the case sensitive name.
    The task for reading and returning case sensitive filename we give to completer in interactive mode
    with ``commands_cache``.
    When listing a XONSH_WIN_PATH_DIRS_TO_LIST dir or using a XONSH_WIN_DIR_SESSION_CACHE cache of a dir listing,
    we can get case sensitive file name.

    Typing speed boost: on Windows instead of checking that 10+ file.pathext files exist it's faster
    to scan a smaller dir and check whether those 10+ strings are in this list
    XONSH_DIR_CACHE_TO_LIST allows users to do just that
    XONSH_WIN_DIR_SESSION_CACHE further allows to list a dir and cache the results to avoid
    doing any IO on subsequent calls
    """
    paths = []
    if env is None:
        env = XSH.env
        env_path = env.get("PATH", [])
        if use_path_cache:  # for generic environment: use cache only if configured
            paths_dict = PathCache.get_clean(env)
            env_path_hash = hash_s_list(env_path)
            if env_path_hash in paths_dict:
                paths = paths_dict[env_path_hash]
            else:
                paths = tuple(clear_paths(env_path))
                PathCache.clean_paths[env_path_hash] = paths
        else:  #              otherwise              : clean paths every time
            paths = tuple(clear_paths(env_path))
    else:  #                  for custom  environment: clean paths every time
        env_path = env.get("PATH", [])
        paths = tuple(clear_paths(env_path))
    path_to_list = env.get("XONSH_DIR_CACHE_TO_LIST", [])
    dir_to_cache = env.get("XONSH_WIN_DIR_SESSION_CACHE", [])
    possible_names = get_possible_names(name, env) if use_pathext else [name]
    ext_count = len(possible_names)

    for path in paths:
        if dir_to_cache and path in dir_to_cache:  # use session dir cache
            F, f = PathCache.get_dir_cached(path)
            if not F:  # not cached, scan the dir ...
                F = []
                for _dirpath, _dirnames, filenames in walk(path):
                    F.extend(filenames)
                    break  # no recursion into subdir
                f = [i.lower() for i in F]
                PathCache.set_dir_cached(path, F, f)  # ... and cache it
            for possible_name in possible_names:
                try:
                    i = f.index(possible_name.lower())
                    possible_Name = F[i]
                except ValueError:
                    continue
                if found := check_possible_name(path, possible_Name, check_executable):
                    return found
                else:
                    continue
        elif (
            ext_count > 2 and path_to_list and path in path_to_list
        ):  # list a dir vs checking many files
            F = []
            for _dirpath, _dirnames, filenames in walk(path):
                F.extend(filenames)
                break  # no recursion into subdir
            f = [i.lower() for i in F]
            for possible_name in possible_names:
                try:
                    i = f.index(possible_name.lower())
                    possible_Name = F[i]
                except ValueError:
                    continue
                if found := check_possible_name(path, possible_Name, check_executable):
                    return found
                else:
                    continue
        else:  # check that file(s) exists individually
            for possible_name in possible_names:
                if found := check_possible_name(path, possible_name, check_executable):
                    return found
                else:
                    continue
