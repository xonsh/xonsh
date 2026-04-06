"""Interfaces to locate executable files on file system."""

import itertools
import os
import time
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
    extensions = list(env.get("PATHEXT", []))
    if not extensions:
        return [name]
    upper = name.upper() == name
    return [name] + [
        name + (ext.upper() if upper else ext.lower()) for ext in extensions
    ]


def clear_paths(paths):
    """Remove duplicates and nonexistent directories from paths."""
    return filter(os.path.isdir, unique_everseen(map(os.path.realpath, paths)))


def get_paths(env=None):
    """Return tuple with deduplicated and existent paths from ``$PATH``."""
    env = env if env is not None else XSH.env
    return tuple(reversed(tuple(clear_paths(env.get("PATH") or []))))


def is_file(filepath):
    """Check that ``filepath`` is file and exist."""
    if isinstance(filepath, str):
        filepath = Path(filepath)
    try:
        if filepath.is_file():
            return True
    except OSError:
        return False
    return False


def is_executable_in_windows(filepath, check_file_exist=True, env=None):
    """Check the file is executable in Windows.

    Parameters
    ----------
    filepath : str
        Path to file.
    check_file_exist : bool
        If ``False`` do not check that file exists. This helps to disable double checking in case the file already
        checked in upstream code. This is important for Windows where checking can take a long time.
    """
    filepath = Path(filepath)
    try:
        if check_file_exist and not is_file(filepath):
            return False
        env = env if env is not None else XSH.env
        return any(s.lower() == filepath.suffix.lower() for s in env.get("PATHEXT", []))
    except FileNotFoundError:
        # On Windows, there's no guarantee for the directory to really
        # exist even if isdir returns True. This may happen for instance
        # if the path contains trailing spaces.
        return False


def is_executable_in_posix(filepath, check_file_exist=True):
    """Check the file is executable in POSIX.

    Parameters
    ----------
    filepath : str
        Path to file.
    check_file_exist : bool
        If ``False`` do not check that file exists. This made to consistency with ``is_executable_in_windows``.
    """
    try:
        if check_file_exist and not is_file(filepath):
            return False
        return os.access(filepath, os.X_OK)
    except OSError:
        # broken Symlink are neither dir not files
        pass
    return False


is_executable = is_executable_in_windows if ON_WINDOWS else is_executable_in_posix


# --- Stable directory listing cache ---
# Directories listed in $XONSH_COMMANDS_CACHE_READ_DIR_ONCE are scanned
# once (on first access) and their file listings are cached as frozensets.
# Any $PATH entry that is under one of these prefixes gets cached.
# This turns per-file stat() calls into O(1) hash lookups.

_stable_dir_cache: dict[str, frozenset[str]] = {}
_stable_prefixes: tuple[str, ...] = ()
_stable_prefixes_source: tuple[str, ...] | None = None  # env snapshot


def _get_stable_prefixes() -> tuple[str, ...]:
    """Return lowered realpath prefixes from $XONSH_COMMANDS_CACHE_READ_DIR_ONCE.

    Re-reads the env var when its value changes (e.g. after ``.append()``).
    """
    global _stable_prefixes, _stable_prefixes_source
    env = XSH.env if XSH.env is not None else {}
    raw = env.get("XONSH_COMMANDS_CACHE_READ_DIR_ONCE", [])
    current = tuple(raw)
    if current != _stable_prefixes_source:
        _stable_prefixes_source = current
        _stable_prefixes = tuple(os.path.realpath(p).lower() for p in raw if p)
    return _stable_prefixes


def _is_stable_dir(path: str) -> bool:
    """Check if *path* is under one of the configured stable prefixes."""
    prefixes = _get_stable_prefixes()
    if not prefixes:
        return False
    rp = os.path.realpath(path).lower()
    return rp.startswith(prefixes)


_stable_dir_reported: set[str] = set()  # Paths already reported as "populate"


def _cached_dir_contains(path: str, filename: str):
    """For stable dirs: check *filename* via cached listing.

    Returns ``(found, populated)`` if the directory is (or was just) cached,
    or ``None`` if it is not a stable directory (caller should stat).

    *populated* is ``True`` on the first **hit** for a freshly-cached path
    (so debug output says "populate cache" on the lookup that actually
    benefits from the new cache, not on an earlier miss).
    """
    if path not in _stable_dir_cache:
        if not _is_stable_dir(path):
            return None
        try:
            files = frozenset(f.lower() for f in os.listdir(path))
        except OSError:
            return None
        _stable_dir_cache[path] = files
    found = filename.lower() in _stable_dir_cache[path]
    populated = False
    if found and path not in _stable_dir_reported:
        _stable_dir_reported.add(path)
        populated = True
    return found, populated


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
                if not is_file(filepath) or (
                    check_executable
                    and not is_executable(filepath, check_file_exist=False)
                ):
                    continue
                return str(filepath.absolute())
            except PermissionError:
                continue


def _cache_debug(msg):
    """Print debug message if $XONSH_COMMANDS_CACHE_DEBUG is True.

    Uses prompt_toolkit's ``print_formatted_text`` when available so the
    message appears above the active prompt without disrupting input.
    """
    env = XSH.env if XSH.env is not None else {}
    if not env.get("XONSH_COMMANDS_CACHE_DEBUG", False):
        return
    try:
        from prompt_toolkit.shortcuts import print_formatted_text

        print_formatted_text(msg)
    except Exception:
        print(msg)


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
    """
    env = env if env is not None else XSH.env
    env_path = env.get("PATH", [])
    paths = tuple(clear_paths(env_path))
    possible_names = get_possible_names(name, env) if use_pathext else [name]
    t0 = time.perf_counter()

    for path, possible_name in itertools.product(paths, possible_names):
        # Fast path: stable directory cache (System32 etc.) — O(1) hash lookup
        cached = _cached_dir_contains(path, possible_name)
        if cached is None:
            pass  # Not a stable dir — fall through to stat below
        elif not cached[0]:
            continue  # Definitely not in this dir — skip without stat
        else:
            found, populated = cached
            # File exists per cache — verify it's a regular file and executable
            filepath = Path(path) / possible_name
            if not is_file(filepath) or (
                check_executable and not is_executable(filepath, check_file_exist=False)
            ):
                continue
            result = str(filepath)
            prefix = "populate cache, get from cache" if populated else "get from cache"
            _cache_debug(
                f"xonsh-commands-cache: {prefix} `{result}` "
                f"({time.perf_counter() - t0:.4f} sec)"
            )
            return result
        # Not a cached dir — original stat-based check
        filepath = Path(path) / possible_name
        try:
            if not is_file(filepath) or (
                check_executable and not is_executable(filepath, check_file_exist=False)
            ):
                continue
            result = str(filepath)
            _cache_debug(
                f"xonsh-commands-cache: get from disk `{result}` "
                f"({time.perf_counter() - t0:.4f} sec)"
            )
            return result
        except PermissionError:
            continue

    _cache_debug(
        f"xonsh-commands-cache: not found `{name}` ({time.perf_counter() - t0:.4f} sec)"
    )
