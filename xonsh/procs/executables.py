"""Interfaces to locate executable files on file system."""

import os
import pickle
import sys
import typing as tp
from os.path import normpath
from pathlib import Path

import pygtrie

from xonsh.built_ins import XSH
from xonsh.lib.itertools import unique_everseen
from xonsh.platform import ON_WINDOWS
from xonsh.tools import ColorShort, print_color


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
    return filter(os.path.isdir, unique_everseen(map(os.path.normpath, paths)))


def get_paths(env=None):
    """Return tuple with deduplicated and existent paths from ``$PATH``."""
    env = env if env is not None else XSH.env
    return tuple(reversed(tuple(clear_paths(env.get("PATH") or []))))


def is_executable_in_windows(filepath, env=None, skip_exist=False):
    """Check the file is executable in Windows."""
    filepath = Path(filepath)
    try:
        if not skip_exist:  # caller checked that a file exists
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


def is_executable_in_posix(filepath, skip_exist=False):
    """Check the file is executable in POSIX."""
    try:
        if skip_exist:  # caller checked that a file exists
            return os.access(filepath, os.X_OK)
        else:
            return filepath.is_file() and os.access(filepath, os.X_OK)
    except OSError:
        # broken Symlink are neither dir not files
        pass
    return False


is_executable = is_executable_in_windows if ON_WINDOWS else is_executable_in_posix


class CmdPart:
    def __init__(self, *args, **kwargs):
        self.is_part: bool = False


def locate_executable(
    name,
    env=None,
    use_path_cache=True,
    path_cache_dirty=False,
    use_dir_cache_session=False,
    use_dir_cache_perma=False,
    partial_match=None,
):
    """Search executable binary name in ``$PATH`` and return full path."""
    return locate_file(
        name,
        env=env,
        check_executable=True,
        use_pathext=True,
        use_path_cache=use_path_cache,
        path_cache_dirty=path_cache_dirty,
        use_dir_cache_session=use_dir_cache_session,
        use_dir_cache_perma=use_dir_cache_perma,
        partial_match=partial_match,
    )


def executables_in(path) -> tp.Iterable[str]:
    """Returns a generator of files in path that the user could execute."""
    if ON_WINDOWS:
        func = _executables_in_windows
    else:
        func = _executables_in_posix
    try:
        yield from func(path)
    except PermissionError:
        return


def _executables_in_posix(path):
    if not os.path.exists(path):
        return
    else:
        yield from _yield_accessible_unix_file_names(path)


def _executables_in_windows(path):
    if not os.path.isdir(path):
        return
    try:
        for x in os.scandir(path):
            if is_executable_in_windows(x):
                yield x.name
    except FileNotFoundError:
        # On Windows, there's no guarantee for the directory to really
        # exist even if isdir returns True. This may happen for instance
        # if the path contains trailing spaces.
        return


def _yield_accessible_unix_file_names(path):
    """yield file names of executable files in path."""
    if not os.path.exists(path):
        return
    for file_ in os.scandir(path):
        if is_executable_in_posix(file_):
            yield file_.name


import threading


class _PathCmd(tp.NamedTuple):
    """A trie of executable files in a given dir with dir's timestamp for cache invalidation"""

    mtime: float
    ftrie: "pygtrie.CharTrie"  # trie[name.lower()] = name for case insensitive match


class PathCache:  # Singleton
    """Avoid IO during typing by caching:
    - cleaned paths (not files/cmds), refreshed per new prompt by setting .is_dirty
    - list of cmds in a "permanent" cache for unchanging dirs, pickled in a cache file
    - list of cmds in a "session" cache for rarely changing dirs
    also contains cleaned up user configured set of paths to cache (normalized, case-matching)
    """

    _instance: tp.Any | None = None
    _lock = threading.Lock()

    def __new__(cls, env):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance.__is_init = False
            cls.env = env
        return cls._instance

    is_dirty = True  # signal to refresh cleaned paths (not files/cmds)
    last_path_hash: str = ""  # avoid the risk of IO on keystroke of clearing Δ paths
    dir_cache_perma: dict[str, pygtrie.CharTrie] = dict()
    dir_cache: dict[str, list[list[str]]] = dict()
    dir_key_cache: dict[str, _PathCmd] = dict()
    clean_paths: dict[str, tuple[str]] = dict()
    CACHE_FILE = "dir_perma_cache.pickle"
    CACHE_FILE_LISTED = "dir_listed_cache.pickle"

    @classmethod
    def reset(cls, delfiles: bool = False):
        """Clean PathCache to allow creating a new one with a different env
        delfiles: Also delete cached files
        """
        self = cls._instance
        if self:
            # cls._instance.__is_init = False
            cls._instance = None
            cls.is_dirty = True
            cls.dir_cache_perma = dict()
            cls.dir_cache = dict()
            cls.dir_key_cache = dict()
            cls.clean_paths = dict()
            if delfiles:
                if self.cache_file and self.cache_file.exists():
                    self.cache_file.unlink(missing_ok=True)
                if self.cache_file_listed and self.cache_file_listed.exists():
                    self.cache_file_listed.unlink(missing_ok=True)

    @classmethod
    def get_clean_paths(cls, env):  # cleaned paths (not files/cmds)
        if cls.is_dirty:
            env_path = env.get("PATH", [])
            env_path_hash = hash_s_list(env_path)  # test match vs. cached PATH
            # returning the cleaned version (avoid wrong cache for a env.swap(PATH=['a']))
            if env_path_hash not in cls.clean_paths:
                cls.clean_paths[env_path_hash] = tuple(clear_paths(env_path))
            cls.last_path_hash = env_path_hash
            cls.is_dirty = False
        return cls.clean_paths

    @classmethod
    def get_clean_path(cls, env) -> tp.Union[tuple[str], None]:
        """Get cleaned paths matching PATH hash, avoiding path cleaning IO unless dirty"""
        paths_dict = cls.get_clean_paths(env)  # updates last_path_hash if dirty
        return paths_dict.get(cls.last_path_hash)

    @classmethod
    def get_dir_cached(cls, path):  # dir_cache_session
        return cls.dir_cache.get(path, None)

    @classmethod
    def set_dir_cached(cls, path, f_trie):  # dir_cache_session
        cls.dir_cache[path] = f_trie

    @classmethod
    def get_dir_key_cache(cls, path):  # dir_cache_key
        return cls.dir_key_cache.get(path, None)

    @classmethod
    def set_dir_key_cache(cls, path, time, f_trie):  # dir_cache_key
        cls.dir_key_cache[path] = _PathCmd(time, f_trie)

    @classmethod
    def get_cache_db(cls, which: str):
        """Get the full cache database
        which: one of 3 types of cache: p|perma|permanent, s|sess|session, l|listed|m|mtime
        """
        if which in ("p", "perma", "permanent"):
            return cls.dir_cache_perma
        elif which in ("s", "sess", "session"):
            return cls.dir_cache
        elif which in ("l", "listed", "m", "mtime"):
            return cls.dir_key_cache
        else:
            print("valid 'which': p|perma|permanent, s|sess|session, l|listed|m|mtime")

    @classmethod
    def help_me_choose(cls, iters: int = 10):
        """Show a table of time costs per dir from $PATH to help select which ones to cache in which type
        iters: # of iterations to run per dir
        """
        c = ColorShort()

        env = cls.env
        self = cls._instance
        if not self:
            print_color(
                f"PathCache isn't initialized yet, so indication of which {c.b}$PATH{c.R} is in which cache isn't available"
            )

        env_path = env.get("PATH", [])
        paths = tuple(clear_paths(env_path))
        pathext = len(env.get("PATHEXT", [])) if ON_WINDOWS else 1
        name = "1ef52612c0d54f0a85c59b61948c12ae"
        possible_names = get_possible_names(name, env)
        ext_count = len(possible_names)

        cat = ["ext", "list_exe", "list_all"]
        cats = {k: k for k in cat}
        cats["ext"] = f"{pathext}·ext"

        import datetime
        import re
        import textwrap
        from math import pow
        from time import monotonic_ns as ttime

        ns = pow(10, 9)  # nanosecond, which 'monotonic_ns' are measured in

        z0 = re.compile(r"(0)(\.)(0+)?", flags=re.X)
        t_paths = dict()
        msg = f"""\
            A ~time estimate of 3 methods of searching for a command in {c.b}$PATH{c.R} (helps choose which dirs to add to which cache):
               • {c.c}ext{c.R}      checks {ext_count} time{"s" if ext_count > 1 else ""} whether a given file.ext exists (≝no cache, precise, slow with many pathext·paths ({int(pathext*ext_count)}) on Windows)
               • {c.c}list_exe{c.R} list all files in a dir, cache only executables (each file is checked) (precise, slow with many files)
               • {c.c}list_all{c.R} list all files in a dir, cache them all (no per-file check) (imprecise, faster vs. list_exe)
            For each method below is a rough time estimate of a single operation in seconds. If {c.c}list_exe{c.R} is comparable to {c.c}ext{c.R} (even if higher), then it should be cached in {c.b}$XONSH_DIR_CACHE_TO_LIST{c.R} even if the dir changes frequently since you'll pay that price once per prompt and only on change instead of once per keystroke regardless of change. If it's high
                • and the dir is changing frequently, but mostly consists of executables (e.g., some {c.c}/bin{c.R} or {c.c}/scripts{c.R} dir), use {c.b}$XONSH_DIR_CACHE_TO_LIST_NON_EXE{c.R}
                • but the dir isn't changing, use {c.b}$XONSH_DIR_PERMA_CACHE{c.R}
                • but the dir isn't changing frequently, consider using {c.b}$XONSH_DIR_SESSION_CACHE{c.R} to pay the price once per session and lose some precision on updates (multiple sessions can use the first session's cache file with {c.b}$XONSH_DIR_SESSION_CACHE_SHARE{c.R})
                • and the dir is changing frequently with mixed exe+non-exe files, avoid caching or use imprecise variants
            (dirs with > 1000 files are only assessed 1 time, not {iters})
            Modified time: color-highlighted if older than 1 week
            Cached labels: P̲ermanent, S̲ession, 'L̲isted'
            """
        print_color(textwrap.dedent(msg))
        header = "   ".join([f"{cats[k]}" for k in cat])
        header += "  # files"
        header += "  # execs"
        header += "   mtime   "
        header += "  Cached?"
        print_color(f"{c.c}{header}{c.R}")
        week_in_sec = 60 * 60 * 24 * 7
        for path in paths:
            is_large_dir = False
            file_count = 0
            exe_count = 0
            t_paths[path] = dict()
            p = Path(path)
            try:
                mtime_f = p.stat().st_mtime
                mtime_r = datetime.datetime.fromtimestamp(
                    mtime_f, tz=datetime.timezone.utc
                )
                mtime_s = mtime_r.strftime("%Y-%m-%d")
                how_old = datetime.datetime.now(tz=datetime.timezone.utc) - mtime_r
                if how_old.total_seconds() > week_in_sec:
                    mtime = f"{c.g}{mtime_s}{c.R}"
                else:
                    mtime = mtime_s
            except Exception:
                mtime = "?".rjust(8)

            # get some stats without impacting later benchmakrs
            for dirpath, _dirnames, filenames in walk(path):
                file_count = len(filenames)
                if file_count > 1000:
                    is_large_dir = True
                for fname in filenames:
                    if is_executable(Path(dirpath) / fname, skip_exist=False):
                        exe_count += 1
                break  # no recursion into subdir

            # list all files and store all files
            t0 = ttime()
            for _ in range(iters):
                for _dirpath, _dirnames, filenames in walk(path):
                    for _fname in filenames:
                        pass
                    break  # no recursion into subdir
                if is_large_dir:
                    break  # don't waste time benchmarking very large dirs
            t1 = ttime()
            iters_real = 1 if is_large_dir else iters
            t_paths[path]["list_all"] = (t1 - t0) / ns / iters_real

            # list all files and store only executables
            t0 = ttime()
            for _ in range(iters):
                for dirpath, _dirnames, filenames in walk(path):
                    for fname in filenames:
                        is_executable(Path(dirpath) / fname, skip_exist=False)
                    break  # no recursion into subdir
                if is_large_dir:
                    break  # don't waste time benchmarking very large dirs
            t1 = ttime()
            t_paths[path]["list_exe"] = (t1 - t0) / ns / iters_real

            # find each pathext executables in
            check_executable = True
            t0 = ttime()
            for _ in range(iters):
                for possible_name in possible_names:
                    filepath = Path(path) / possible_name
                    try:
                        if not filepath.is_file() or (
                            check_executable
                            and not is_executable(filepath, skip_exist=True)
                        ):
                            continue
                        break
                    except PermissionError:
                        continue
            t1 = ttime()
            t_paths[path]["ext"] = (t1 - t0) / ns / iters

            s_out = {k: "" for k in cat}
            for k in s_out:
                c_pre, c_pos = "", ""
                if not k == "list_all" and t_paths[path][k] == min(
                    [
                        t_paths[path]["list_exe"],
                        t_paths[path]["ext"],
                    ]
                ):
                    c_pre = c.g
                    c_pos = c.R
                s = f"{t_paths[path][k]:.4f}"
                m = re.match(z0, s)
                if m:
                    z0pos_len = len(m.groups()[2]) if m.groups()[2] else 0
                    s_out[k] = c_pre + re.sub(z0, f" .{' '*z0pos_len}", s) + c_pos
                else:
                    s_out[k] = c_pre + s + c_pos

            res = "   ".join([f"{v}" for v in s_out.values()])

            # Check which PATHs are cached and where
            pn = os.path.normpath(path)
            lbl = ""
            if (
                pn in self.usr_dir_list_perma
                or pn in self.usr_dir_list_session
                or pn in self.usr_dir_list_key
                or pn in self.usr_dir_alist_key
            ):
                lbl += "✓ "
            else:
                lbl += " ✗"
            lbl += "P" if pn in self.usr_dir_list_perma else " "
            lbl += "S" if pn in self.usr_dir_list_session else " "
            lbl += "L" if pn in self.usr_dir_list_key else " "
            lbl += "A" if pn in self.usr_dir_alist_key else " "
            file_count_s = f"{file_count}".rjust(6)
            exec_count_s = f"{exe_count}".rjust(6)
            res += f"       {file_count_s}   {exec_count_s}  {mtime}  {lbl}   {path}"
            print_color(res)

    def get_cache_info(self, v=0):
        """Show some basic path cache info, v: verbosity level 0–2. Example:
        from xonsh.procs.executables import PathCache; pc = PathCache(None); pc.get_cache_info(v=2)
        """
        import textwrap

        env = self.__class__.env
        env_path = env.get("PATH", [])
        env_path_hash = hash_s_list(env_path)
        if env_path_hash not in PathCache.clean_paths:
            print("hash not in clean_paths")
        clean_paths = PathCache.clean_paths.get(
            env_path_hash, tuple(clear_paths(env_path))
        )
        cached_perma, cached_sess, cached_list, cached_alist = 0, 0, 0, 0
        list_perma, list_sess, list_list, list_alist = [], [], [], []
        uncached = []
        for p in clean_paths:
            inc_perma, inc_sess, inc_list, inc_alist = 0, 0, 0, 0
            if p in self.usr_dir_list_perma:
                inc_perma = True
                cached_perma += 1
                list_perma.append(p)
            if p in self.usr_dir_list_session:
                inc_sess = True
                cached_sess += 1
                list_sess.append(p)
            if p in self.usr_dir_list_key:
                inc_list = True
                cached_list += 1
                list_list.append(p)
            if p in self.usr_dir_alist_key:
                inc_alist = True
                cached_alist += 1
                list_alist.append(p)
            if not (inc_perma or inc_sess or inc_list or inc_alist):
                uncached.append(p)
        uncached_c = len(uncached)
        ext_min = int(env.get("XONSH_DIR_CACHE_LIST_EXT_MIN"))
        cached = cached_perma + cached_sess + cached_list + cached_alist
        skip_exist = "✓" if env.get("XONSH_DIR_CACHE_SKIP_EXIST", True) else "✗"
        c = ColorShort()
        msg = f"""\
            PATH    : ∑ {str(len(env_path   )).rjust(3)} dirty
                      └ {str(len(clean_paths)).rjust(3)} clean (unique & existing)
            Cached  : ∑ {str(    cached      ).rjust(3)} of which:               ({c.b}pc = PathCache(None){c.R}pc.usr_dir_list_perma)
                      ├ {str(cached_perma    ).rjust(3)} permanently             ({c.b}pc.usr_dir_list_perma  {c.R} ← $XONSH_DIR_PERMA_CACHE   )
                      ├ {str(cached_sess     ).rjust(3)} this session            ({c.b}pc.usr_dir_list_session{c.R} ← $XONSH_DIR_SESSION_CACHE )
                      ├ {str(cached_list     ).rjust(3)} by dir mtime ('Listed') ({c.b}pc.usr_dir_list_key    {c.R} ← $XONSH_DIR_CACHE_TO_LIST )
                      └ {str(cached_alist    ).rjust(3)} by dir mtime ('AListed')({c.b}pc.usr_dir_alist_key   {c.R} ← $XONSH_DIR_CACHE_TO_ALIST)\
        """
        if v >= 1:
            msg += f"""
                                                   ({str(ext_min     ).rjust(2)}                        $XONSH_DIR_CACHE_LIST_EXT_MIN)\
        """
        msg += f"""
            Uncached: ∑ {str(uncached_c      ).rjust(3)}{' including:' if uncached_c else ''}\
        """
        if v >= 1:
            msg += f"""
                                                   ({       skip_exist.rjust(2)}                        $XONSH_DIR_CACHE_SKIP_EXIST  )\
        """
        print_color(textwrap.dedent(msg))
        msg = ""
        if uncached:
            msg += "  " + "\n  ".join(uncached)
        if v >= 1:
            msg += (
                "\n"
                + str(len(list_perma))
                + " paths cached permanently :\n  "
                + "\n  ".join(list_perma)
            )
            msg += (
                "\n"
                + str(len(list_sess))
                + " paths cached this session:\n  "
                + "\n  ".join(list_sess)
            )
            msg += (
                "\n"
                + str(len(list_list))
                + " paths cached by dir mtime ('listed'):\n  "
                + "\n  ".join(list_list)
            )
            msg += (
                "\n"
                + str(len(list_alist))
                + " paths cached by dir mtime ('alisted'):\n  "
                + "\n  ".join(list_alist)
            )
        if v >= 2:
            # print(f"PATH #{len(env_path)}    :\n  {'\n  '.join(env_path)}")
            msg += f"\n\n{len(env_path)} $PATH:\n ✓✗  Cached/Not (Perma, Session, 'Listed', 'AListed')\n   - Doesn't exist"
            for p in env_path:
                pn = os.path.normpath(p)
                lbl = ""
                if (
                    pn in self.usr_dir_list_perma
                    or pn in self.usr_dir_list_session
                    or pn in self.usr_dir_list_key
                    or pn in self.usr_dir_alist_key
                ):
                    lbl += "✓ "
                else:
                    lbl += " ✗"
                lbl += " " if pn in clean_paths else "-"
                lbl += "P" if pn in self.usr_dir_list_perma else " "
                lbl += "S" if pn in self.usr_dir_list_session else " "
                lbl += "L" if pn in self.usr_dir_list_key else " "
                lbl += "A" if pn in self.usr_dir_alist_key else " "
                msg += f"\n {lbl} {p}"
        msg += (
            "\n\n"
            + ("✓" if env.get("XONSH_DIR_CWD_CACHE", False) else "✗")
            + " current working dir cache ($XONSH_DIR_CWD_CACHE)\n"
        )
        if v >= 1:
            msg += (
                "\n"
                "Cached file data: pc = PathCache with key = path, value = (mtime+) trie of files|commands (depending on …_NON_EXE))\n"
                + f"  Permanent : {c.b}pc.get_cache_db('p'){c.R}  ($XONSH_DIR_PERMA_CACHE                         )\n"
                + f"  Session   : {c.b}pc.get_cache_db('s'){c.R}  ($XONSH_DIR_SESSION_CACHE                       )\n"
                + f"  'Listed'  : {c.b}pc.get_cache_db('l'){c.R}  ($XONSH_DIR_CACHE_TO_LIST + $XONSH_DIR_CWD_CACHE)\n"
            )
        if env.get("XONSH_DIR_CWD_CACHE", False):
            msg += (
                "✓" if env.get("XONSH_DIR_CWD_CACHE_NON_EXE", False) else "✗"
            ) + " (cwd) cache non-executable ({c.b}$XONSH_DIR_CWD_CACHE_NON_EXE){c.R}"
        if len(self.cwd_too_long):
            msg += (
                f"\n {len(self.cwd_too_long)} cwdirs found with # of items > "
                + env.get("XONSH_DIR_CWD_CACHE_LEN_MAX")
            )
            if v >= 2:
                msg += ":\n"
                msg += "\n  ".join(self.cwd_too_long)
        print_color(msg)

    def __init__(self, env) -> None:
        self.__is_init: bool
        if self.__is_init:
            self.set_usr_dir_list(env)
            return
        # file paths storing [dir_cache,pathext_cache] for pre-loading
        self._cache_file = None
        self._cache_file_listed = None
        self._cmds_cache: pygtrie.CharTrie = pygtrie.CharTrie()
        self._pathext_cache: set = set()
        self._pathext_cache_list: set = set()
        self._user_path_dirs_to_list: set = set()
        self.usr_dir_list_perma: set = set()
        self.usr_dir_list_session: set = set()
        self.usr_dir_list_key: set = set()
        self.usr_dir_alist_key: set = set()
        self._usr_dir_list_perma = None  # save last valid to check for updates
        self._usr_dir_list_session = None
        self._usr_dir_list_key = None
        self._usr_dir_alist_key = None
        self.cwd_too_long: set = set()
        self.set_usr_dir_list(env)
        self.load_cache_listed()
        self.__is_init = True

    def set_usr_dir_list(self, env) -> None:
        """Clean up user lists of dirs-to-be-cached and save them. Also include dirs not in PATH since they can be added to PATH later (even on startup by a plugin)."""
        if self.__class__.is_dirty:
            dir_list = env.get("XONSH_DIR_PERMA_CACHE", [])
            if not dir_list == self._usr_dir_list_perma:
                self._usr_dir_list_perma = dir_list
                self.usr_dir_list_perma = set(normpath(p) for p in dir_list)
            dir_list = env.get("XONSH_DIR_SESSION_CACHE", [])
            if not dir_list == self._usr_dir_list_session:
                self._usr_dir_list_session = dir_list
                self.usr_dir_list_session = set(normpath(p) for p in dir_list)
            dir_list = env.get("XONSH_DIR_CACHE_TO_LIST", [])
            if not dir_list == self._usr_dir_list_key:
                self._usr_dir_list_key = dir_list
                self.usr_dir_list_key = set(normpath(p) for p in dir_list)
            dir_list = env.get("XONSH_DIR_CACHE_TO_ALIST", [])
            if not dir_list == self._usr_dir_alist_key:
                self._usr_dir_alist_key = dir_list
                self.usr_dir_alist_key = set(normpath(p) for p in dir_list)
        if not self.__is_init:
            # just in case, add dirs from PATH with a different case
            usr_dir_list_perma_pl = [p.lower() for p in self.usr_dir_list_perma]
            usr_dir_list_session_pl = [p.lower() for p in self.usr_dir_list_session]
            usr_dir_list_key_pl = [p.lower() for p in self.usr_dir_list_key]
            usr_dir_alist_key_pl = [p.lower() for p in self.usr_dir_alist_key]
            env_path = env.get("PATH", [])
            for p in env_path:
                pn = normpath(p)
                pl = pn.lower()
                if pl in usr_dir_list_perma_pl:
                    self.usr_dir_list_perma.add(pn)
                if pl in usr_dir_list_session_pl:
                    self.usr_dir_list_session.add(pn)
                if pl in usr_dir_list_key_pl:
                    self.usr_dir_list_key.add(pn)
                if pl in usr_dir_alist_key_pl:
                    self.usr_dir_alist_key.add(pn)

    @property
    def cache_file(self):
        """Path to the cache file with "permanent" dir info (on instance-attr)"""
        env = self.__class__.env
        if self._cache_file is None:
            if env.get("XONSH_CACHE_DIR") and env.get("XONSH_DIR_PERMA_CACHE"):
                self._cache_file = (
                    Path(env["XONSH_CACHE_DIR"]).joinpath(self.CACHE_FILE).resolve()
                )
            else:
                self._cache_file = ""  # set a falsy value other than None
        return self._cache_file

    @property
    def cache_file_listed(self):
        """Path to the cache file with "listed/mtimed" dir info (on instance-attr)"""
        env = self.__class__.env
        if self._cache_file_listed is None:
            if env.get("XONSH_CACHE_DIR") and (
                env.get("XONSH_DIR_CACHE_TO_LIST") or env.get("XONSH_DIR_CWD_CACHE")
            ):
                self._cache_file_listed = (
                    Path(env["XONSH_CACHE_DIR"])
                    .joinpath(self.CACHE_FILE_LISTED)
                    .resolve()
                )
            else:
                self._cache_file_listed = ""  # set a falsy value other than None
        return self._cache_file_listed

    def get_dir_cache_perma(self, was_dirty: bool = False):
        """Get a list of valid commands per path in a trie data structure for partial matching
        was_dirty: skip update risk (triggering IO) on each keystroke (is_dirty is set for a new prompt)"""
        if was_dirty:
            self.update_cache()
        return self.__class__.dir_cache_perma

    def update_cache(self):
        """The main function to update commands cache"""
        paths = self.get_clean_path(self.__class__.env)

        if paths and self._update_paths_cache(paths):
            pass  # not yet needed since only a few dirs are supported
        #     all_cmds = pygtrie.CharTrie()
        #     for cmd_low, cmd, path in self._iter_binaries(reversed(paths)): # iterate backwards for entries @ PATH front to overwrite entries at the back
        #         all_cmds[cmd_low] = (cmd,path)
        #     self._cmds_cache = all_cmds
        # return self._cmds_cache

    def _shrink_dir_cache_perma(self, rm_pathext: set[str]) -> None:
        for pathext_lc in set(ext.lower() for ext in rm_pathext):  # ref, so updates…
            for cmd_chartrie in self.__class__.dir_cache_perma.values():
                for cmd_lower in cmd_chartrie.keys():
                    if cmd_lower.endswith(pathext_lc):
                        cmd_chartrie.pop(cmd_lower, None)  # … when del here

    def _update_paths_cache(self, paths: tp.Sequence[str]) -> bool:
        """load cached results or update cache"""
        if (
            (not self.__class__.dir_cache_perma)
            and self.cache_file
            and self.cache_file.exists()
        ):
            try:  # load commands from cache-file if configured
                [self.__class__.dir_cache_perma, self._pathext_cache] = pickle.loads(
                    self.cache_file.read_bytes()
                ) or [dict(), set()]
            except Exception as e:
                print(
                    f"failed to load 'Permanent' dir cache, deleting it @ {self.cache_file}: {e}",
                    file=sys.stderr,
                )
                self.cache_file.unlink(missing_ok=True)
        updated = False
        pathext = set(self.__class__.env.get("PATHEXT", [])) if ON_WINDOWS else set()
        is_exe_def_valid = (pathext == self._pathext_cache) or (
            not pathext and not self._pathext_cache
        )  # ≝ of an executable NOT changed
        if not is_exe_def_valid:  # invalidate existing cache
            self._pathext_cache = pathext
            rm_pathext = self._pathext_cache - pathext
            if ON_WINDOWS and rm_pathext:  # fewer pathexts
                self._shrink_dir_cache_perma(rm_pathext)  # remove without rebuilding
                is_exe_def_valid = True
            else:
                self.__class__.dir_cache_perma = dict()
        for path in paths:  # ↓ user-configured to be cached
            if (path in self.usr_dir_list_perma) and (
                (path not in self.__class__.dir_cache_perma)  # ← not in cache
                or not is_exe_def_valid
            ):
                cmd_chartrie = pygtrie.CharTrie()
                for cmd in executables_in(path):
                    # case-insensitive ↓ search, ↓ but preserve case
                    cmd_chartrie[cmd.lower()] = cmd
                self.__class__.dir_cache_perma[path] = cmd_chartrie
                updated = True
        if updated and self.cache_file:
            self.cache_file.write_bytes(
                pickle.dumps([self.__class__.dir_cache_perma, self._pathext_cache])
            )
        return updated

    @classmethod
    def load_cache_listed(cls):
        """Load cached 'Listed' dirs to file (on startup not to dupe-list dir if no mtime changed)"""
        self = cls._instance
        if not self:
            return
        dir_cache, pathext_cache = None, None
        if self.cache_file_listed and self.cache_file_listed.exists():
            try:  # load commands from cache-file if configured
                [dir_cache, pathext_cache] = pickle.loads(
                    self.cache_file_listed.read_bytes()
                )
            except Exception as e:
                print(
                    f"Failed to load 'Listed' dir cache, deleting it @ {self.cache_file_listed}: {e}",
                    file=sys.stderr,
                )
                self.cache_file_listed.unlink(missing_ok=True)

            pathext = set(cls.env.get("PATHEXT", [])) if ON_WINDOWS else set()
            is_exe_def_valid = (
                pathext == pathext_cache
            )  # ≝ of an executable NOT changed
            cls.dir_key_cache = dir_cache if is_exe_def_valid else dict()
            self._pathext_cache_list = pathext_cache if is_exe_def_valid else set()
            # if not is_exe_def_valid: # will be overwritten on exit, so no point in del?
            #     # print(f"Stale 'Listed' dir cache, deleting it…")
            #     cls.cache_file_listed.unlink(missing_ok=True)

    @classmethod
    def save_cache_listed(cls):
        """Save cached 'Listed' dirs to file (on exit)"""
        self = cls._instance
        if not self:
            return
        dir_cache = cls.dir_key_cache
        pathext_cache = set(cls.env.get("PATHEXT", [])) if ON_WINDOWS else set()
        if self.cache_file_listed:
            try:  # save commands to cache-file if configured
                self.cache_file_listed.write_bytes(
                    pickle.dumps([dir_cache, pathext_cache])
                )
            except Exception as e:
                print(
                    f"Failed to save 'Listed' dir cache it @ {self.cache_file_listed}: {e}",
                    file=sys.stderr,
                )

    def _iter_binaries(self, paths):
        for path in paths:
            for cmd_low in (
                cmd_chartrie := self.__class__.dir_cache_perma.get(path, [])
            ):
                cmd = cmd_chartrie[cmd_low]
                yield cmd_low, cmd, os.path.join(path, cmd)


def locate_file(
    name,
    env=None,
    check_executable=False,
    use_pathext=False,
    use_path_cache=True,
    path_cache_dirty=False,
    use_dir_cache_session=False,
    use_dir_cache_perma=False,
    partial_match=None,
):
    """Search file name in the current working directory and in ``$PATH`` and return full path."""
    return locate_relative_path(
        name, env, check_executable, use_pathext, partial_match
    ) or locate_file_in_path_env(
        name,
        env,
        check_executable,
        use_pathext,
        use_path_cache,
        path_cache_dirty,
        use_dir_cache_session,
        use_dir_cache_perma,
        partial_match,
    )


def locate_relative_path(
    name, env=None, check_executable=False, use_pathext=False, partial_match=None
):
    """Return absolute path by relative file path.

    We should not locate files without prefix (e.g. ``"binfile"``) by security reasons like other shells.
    If directory has "binfile" it can be called only by providing prefix "./binfile" explicitly.
    """
    p = Path(name)
    prefixes = ("./", "../", ".\\", "..\\", "~/")
    has_prefix = name.startswith(prefixes)
    if has_prefix or p.is_absolute():
        env = env if env else XSH.env
        cache_non_exe = env.get("XONSH_DIR_CWD_CACHE_NON_EXE", True)
        is_cache_cwd = env.get("XONSH_DIR_CWD_CACHE", False)
        skip_exist = env.get("XONSH_DIR_CACHE_SKIP_EXIST", False)
        pc = PathCache(env)
        possible_names = get_possible_names(p.name, env) if use_pathext else [p.name]

        if is_cache_cwd and p not in pc.cwd_too_long:
            name_clean = name
            if has_prefix:  # relative, remove prefix
                for pref in prefixes:
                    if name.startswith(pref):
                        name_clean = name.removeprefix(pref)
                        break
            elif p.name:  # absolute, get name
                name_clean = p.name
            path = p.parent
            path_time = os.path.getmtime(path)
            path_cmd = pc.get_dir_key_cache(path)
            use_cache = True if path_cmd and (path_cmd.mtime == path_time) else False
            if use_cache:
                ftrie = path_cmd.ftrie
            else:  # rebuild dir cache
                skip_exist = True  # no dupe is_file: we list files
                ftrie = pygtrie.CharTrie()
                for dirpath, _dirnames, filenames in walk(path):
                    if len(filenames) > env.get("XONSH_DIR_CWD_CACHE_LEN_MAX", 500):
                        pc.cwd_too_long.add(path)
                    for fname in filenames:
                        if cache_non_exe:  # ↓for case-insensitive match
                            ftrie[fname.lower()] = fname
                        elif is_executable(Path(dirpath) / fname, skip_exist):
                            ftrie[fname.lower()] = fname
                    break  # no recursion into subdir
                pc.set_dir_key_cache(path, path_time, ftrie)
            for possible_name in possible_names:
                possible_Name = ftrie.get(possible_name.lower())
                if possible_Name is not None:  #          ✓ full match
                    if found := check_possible_name(
                        path, possible_Name, check_executable, skip_exist
                    ):
                        return found
                    else:
                        continue
            if ftrie.has_subtrie(name_clean.lower()):  # ± partial match
                if isinstance(partial_match, CmdPart):
                    partial_match.is_part = True  # for color highlighting
        else:
            for possible_name in possible_names:
                filepath = p.parent / possible_name
                try:
                    if not filepath.is_file() or (
                        check_executable
                        and not is_executable(filepath, skip_exist=True)
                    ):
                        continue
                    return str(p.absolute())
                except PermissionError:
                    continue


from os import walk


def check_possible_name(path, possible_name, check_executable, skip_exist=False):
    filepath = Path(path) / possible_name
    try:
        if check_executable and not is_executable(filepath, skip_exist=skip_exist):
            return
        if not skip_exist and not filepath.is_file():
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
    for s in s_list:  # Hash each string
        length_encoded = struct.pack("I", len(s))
        hash_o.update(length_encoded)
        hash_o.update(s.encode("utf-8"))
    return hash_o.hexdigest()


def locate_file_in_path_env(
    name,
    env=None,
    check_executable=False,
    use_pathext=False,
    use_path_cache=True,
    path_cache_dirty=False,
    use_dir_cache_session=False,
    use_dir_cache_perma=False,
    partial_match=None,
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
    When listing a XONSH_DIR_CACHE_TO_LIST dir or using a XONSH_DIR_SESSION_CACHE cache of a dir listing,
    we can get case sensitive file name.

    Typing speed boost: on Windows instead of checking that 10+ file.pathext files exist it's faster
    to scan a smaller dir and check whether those 10+ strings are in this list
    XONSH_DIR_CACHE_TO_LIST allows users to do just that
    XONSH_DIR_SESSION_CACHE further allows to list a dir and cache the results to avoid
    doing any IO on subsequent calls
    XONSH_DIR_PERMA_CACHE further allows to list larger constant dirs like Windows/System32
    and cache the results until OS is updated to avoid doing any IO
    """
    paths = []
    pc = PathCache(env if env is not None else XSH.env)
    was_dirty = pc.is_dirty
    if env is None:
        env = XSH.env
        if use_path_cache:  # for generic environment: use cache only if configured
            if not path_cache_dirty:  # avoid clear_paths IO
                PathCache.is_dirty = True  # updates path hash (≝each prompt)
                was_dirty = True
            paths = PathCache.get_clean_path(env)
        else:  #              otherwise              : clean paths
            env_path = env.get("PATH", [])
            paths = tuple(clear_paths(env_path))
    else:  #                  for custom  environment: clean paths every time
        env_path = env.get("PATH", [])
        paths = tuple(clear_paths(env_path))
    if pc.usr_dir_list_perma:  # path → cmd_chartrie[cmd.lower()] = cmd
        dir_cache_perma = pc.get_dir_cache_perma(was_dirty)
    possible_names = get_possible_names(name, env) if use_pathext else [name]
    ext_count = len(possible_names)
    ext_min = int(env.get("XONSH_DIR_CACHE_LIST_EXT_MIN", 3))
    skip_exist = env.get(
        "XONSH_DIR_CACHE_SKIP_EXIST", False
    )  # avoid dupe is_file check since we assume permanent/session caches don't change ever/per session

    for path in paths:
        if (
            check_executable
            and use_dir_cache_perma
            and pc.usr_dir_list_perma
            and path in pc.usr_dir_list_perma
            and path in dir_cache_perma
        ):
            cmd_chartrie = dir_cache_perma[path]
            for possible_name in possible_names:
                possible_Name = cmd_chartrie.get(possible_name.lower())
                if possible_Name is not None:  #          ✓ full match
                    if found := check_possible_name(
                        path, possible_Name, check_executable, skip_exist
                    ):
                        return found
                    else:
                        continue
            if cmd_chartrie.has_subtrie(name.lower()):  # ± partial match
                if isinstance(
                    partial_match, CmdPart
                ):  # report partial match for color highlighting
                    partial_match.is_part = True
        elif (
            use_dir_cache_session
            and pc.usr_dir_list_session
            and path in pc.usr_dir_list_session
        ):  # use session dir cache
            f_trie = PathCache.get_dir_cached(path)
            if not f_trie:  # not cached, scan the dir ...
                f_trie = pygtrie.CharTrie()
                for _dirpath, _dirnames, filenames in walk(path):
                    for fname in filenames:
                        f_trie[fname.lower()] = fname  # for case-insensitive match
                    break  # no recursion into subdir
                PathCache.set_dir_cached(path, f_trie)  # ... and cache it
            for possible_name in possible_names:
                possible_Name = f_trie.get(possible_name.lower())
                if possible_Name is not None:  #          ✓ full match
                    if found := check_possible_name(
                        path, possible_Name, check_executable, skip_exist
                    ):
                        return found
                    else:
                        continue
            if f_trie.has_subtrie(name.lower()):  # ± partial match
                if isinstance(
                    partial_match, CmdPart
                ):  # report partial match for color highlighting
                    partial_match.is_part = True
        elif ext_count >= ext_min and (
            (pc.usr_dir_list_key and path in pc.usr_dir_list_key)
            or (pc.usr_dir_alist_key and path in pc.usr_dir_alist_key)
        ):  # list a dir vs checking many files (cached by mtime)
            cache_non_exe = path in pc.usr_dir_alist_key
            path_time = os.path.getmtime(path)
            path_cmd = PathCache.get_dir_key_cache(path)
            use_cache = True if path_cmd and (path_cmd.mtime == path_time) else False
            if use_cache:
                ftrie = path_cmd.ftrie
            else:  # rebuild dir cache
                skip_exist = True  # no dupe is_file: we list files
                ftrie = pygtrie.CharTrie()
                for dirpath, _dirnames, filenames in walk(path):
                    for fname in filenames:
                        if cache_non_exe:  # ↓for case-insensitive match
                            ftrie[fname.lower()] = fname
                        elif is_executable(Path(dirpath) / fname, skip_exist):
                            ftrie[fname.lower()] = fname
                    break  # no recursion into subdir
                PathCache.set_dir_key_cache(path, path_time, ftrie)
            for possible_name in possible_names:
                possible_Name = ftrie.get(possible_name.lower())
                if possible_Name is not None:  #          ✓ full match
                    if found := check_possible_name(
                        path, possible_Name, check_executable, skip_exist
                    ):
                        return found
                    else:
                        continue
            if ftrie.has_subtrie(name.lower()):  # ± partial match
                if isinstance(
                    partial_match, CmdPart
                ):  # report partial match for color highlighting
                    partial_match.is_part = True
        else:  # check that file(s) exists individually
            for possible_name in possible_names:
                if found := check_possible_name(path, possible_name, check_executable):
                    return found
                else:
                    continue
