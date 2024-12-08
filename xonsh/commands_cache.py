"""Module for caching command & alias names as well as for predicting whether
a command will be able to be run in the background.

A background predictor is a function that accepts a single argument list
and returns whether or not the process can be run in the background (returns
True) or must be run the foreground (returns False).
"""

import argparse
import collections.abc as cabc
import os
import pickle
import time
import typing as tp
from pathlib import Path

from xonsh.lib.lazyasd import lazyobject
from xonsh.platform import ON_POSIX, ON_WINDOWS, pathbasename
from xonsh.procs.executables import (
    get_paths,
    get_possible_names,
    is_executable_in_posix,
    is_executable_in_windows,
)


class CaseInsensitiveDict(dict[tp.Any, tp.Any]):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._store = {}
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        # Store the key in lowercase but preserve the original case for display
        self._store[key.casefold()] = key
        super().__setitem__(key.casefold(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.casefold())

    def __delitem__(self, key):
        del self._store[key.casefold()]
        super().__delitem__(key.casefold())

    def __contains__(self, key):
        return key.casefold() in self._store

    def get(self, key, default=None):
        return super().get(key.casefold(), default)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def keys(self):
        # Return the original keys with their original casing
        return (self._store[k] for k in self._store)

    def items(self):
        return ((self._store[k], self[k]) for k in self._store)

    def __repr__(self):
        return f"{self.__class__.__name__}({dict(self.items())})"

    def copy(self):
        return CaseInsensitiveDict(self.items())


CacheDict: tp.Union[type[CaseInsensitiveDict], type[dict]]
if ON_WINDOWS:
    CacheDict = CaseInsensitiveDict
else:
    CacheDict = dict


class _Commands(tp.NamedTuple):
    mtime: float
    cmds: "tuple[str, ...]"


def _yield_accessible_unix_file_names(path):
    """yield file names of executable files in path."""
    if not os.path.exists(path):
        return
    for file_ in os.scandir(path):
        if is_executable_in_posix(file_):
            yield file_.name


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


class CommandsCache(cabc.Mapping):
    """A lazy cache representing the commands available on the file system.
    The keys are the command names and the values a tuple of (loc, has_alias)
    where loc is either a str pointing to the executable on the file system or
    None (if no executable exists) and has_alias is a boolean flag for whether
    the command has an alias.

    Note! There is ``xonsh.procs.executables`` module with resolving executables.
    Usage ``executables`` is preferred instead of commands_cache for cases
    where you just need to locate executable command.
    """

    CACHE_FILE = "path-commands-cache.pickle"

    def __init__(self, env, aliases=None) -> None:
        # cache commands in path by mtime
        self._paths_cache: dict[str, _Commands] = {}

        # wrap aliases and commands in one place
        self._cmds_cache: dict[str, tuple[str, bool | None]] = {}

        self._alias_checksum: int | None = None
        self.threadable_predictors = default_threadable_predictors()

        # Path to the cache-file where all commands/aliases are cached for pre-loading"""
        self.env = env
        if aliases is None:
            from xonsh.aliases import Aliases, make_default_aliases

            self.aliases = Aliases(make_default_aliases())
        else:
            self.aliases = aliases
        self._cache_file = None

    @property
    def cache_file(self):
        """Keeping a property that lies on instance-attribute"""
        env = self.env
        # Path to the cache-file where all commands/aliases are cached for pre-loading
        if self._cache_file is None:
            if "XONSH_CACHE_DIR" in env and env.get("COMMANDS_CACHE_SAVE_INTERMEDIATE"):
                self._cache_file = (
                    Path(env["XONSH_CACHE_DIR"]).joinpath(self.CACHE_FILE).resolve()
                )
            else:
                # set a falsy value other than None
                self._cache_file = ""

        return self._cache_file

    def __contains__(self, key):
        self.update_cache()
        return self.lazyin(key)

    def __iter__(self):
        for cmd, _ in self.iter_commands():
            yield cmd

    def iter_commands(self):
        """Wrapper for handling windows path behaviour"""
        return self.all_commands.items()

    def __len__(self):
        return len(self.all_commands)

    def __getitem__(self, key) -> "tuple[str, bool]":
        self.update_cache()
        return self.lazyget(key)

    def is_empty(self):
        """Returns whether the cache is populated or not."""
        return len(self._cmds_cache) == 0

    def get_possible_names(self, name):
        return get_possible_names(name, self.env)

    def _update_aliases_cache(self):
        """Update aliases checksum and return result: updated or not."""
        prev_hash = self._alias_checksum
        self._alias_checksum = hash(frozenset(self.aliases))
        return prev_hash != self._alias_checksum

    def _update_and_check_changes(self, paths: tuple[str, ...]):
        """Update cache and return the result: updated or still the same.

        Be careful in this place. Both `_update_*` functions must be called
        because they are changing state after update.
        """
        is_aliases_change = self._update_aliases_cache()
        is_paths_change = self._update_paths_cache(paths)
        return is_aliases_change or is_paths_change

    @property
    def all_commands(self):
        self.update_cache()
        return self._cmds_cache

    def resolve_symlink(self, path):
        visited = set()
        current_path = path
        while os.path.islink(current_path):
            if current_path in visited:
                # Detected a loop while resolving symlink
                return None
            visited.add(current_path)
            try:
                current_path = os.readlink(current_path)
            except Exception:
                return None
            if not os.path.isabs(current_path):
                current_path = os.path.join(os.path.dirname(path), current_path)
                current_path = os.path.normpath(current_path)

        if current_path == path:
            return None

        return current_path

    def update_cache(self):
        """The main function to update commands cache.
        Note! There is ``xonsh.procs.executables`` module with resolving executables.
        Usage ``executables`` is preferred instead of commands_cache for cases
        where you just need to locate executable command.
        """
        env = self.env
        # iterate backwards so that entries at the front of PATH overwrite
        # entries at the back.
        paths = get_paths(env)
        if self._update_and_check_changes(paths):
            all_cmds = CacheDict()
            for cmd, path in self._iter_binaries(paths):
                # None     -> not in aliases
                all_cmds[cmd] = (path, None)

            # aliases override cmds
            for cmd in self.aliases:
                # Get the possible names the alias could be overriding,
                # and check if any are in all_cmds.
                possibilities = self.get_possible_names(cmd)
                override_key = next(
                    (possible for possible in possibilities if possible in all_cmds),
                    None,
                )
                if override_key:
                    # (path, False) -> has same named alias
                    all_cmds[override_key] = (all_cmds[override_key][0], False)
                else:
                    # True -> pure alias
                    all_cmds[cmd] = (cmd, True)
            self._cmds_cache = all_cmds
        return self._cmds_cache

    def _update_paths_cache(self, paths: tp.Sequence[str]) -> bool:
        """load cached results or update cache"""
        if (not self._paths_cache) and self.cache_file and self.cache_file.exists():
            # first time load the commands from cache-file if configured
            try:
                self._paths_cache = pickle.loads(self.cache_file.read_bytes()) or {}
            except Exception:
                # the file is corrupt
                self.cache_file.unlink(missing_ok=True)

        updated = False
        for path in paths:
            modified_time = os.path.getmtime(path)
            if (
                (not self.env.get("ENABLE_COMMANDS_CACHE", True))
                or (path not in self._paths_cache)
                or (self._paths_cache[path].mtime != modified_time)
            ):
                updated = True
                self._paths_cache[path] = _Commands(
                    modified_time, tuple(executables_in(path))
                )

        if updated and self.cache_file:
            self.cache_file.write_bytes(pickle.dumps(self._paths_cache))
        return updated

    def _iter_binaries(self, paths):
        for path in paths:
            for cmd in self._paths_cache[path].cmds:
                yield cmd, os.path.join(path, cmd)

    def cached_name(self, name):
        """Returns the name that would appear in the cache, if it exists."""
        cached = pathbasename(name) if os.pathsep in name else name
        keys = self.get_possible_names(cached)
        return next((k for k in keys if k in self._cmds_cache), name)

    def lazyin(self, key):
        """Checks if the value is in the current cache without the potential to
        update the cache. It just says whether the value is known *now*. This
        may not reflect precisely what is on the $PATH.
        """
        return self.cached_name(key) in self._cmds_cache

    def lazyiter(self):
        """Returns an iterator over the current cache contents without the
        potential to update the cache. This may not reflect what is on the
        $PATH.
        """
        return iter(self._cmds_cache)

    def lazylen(self):
        """Returns the length of the current cache contents without the
        potential to update the cache. This may not reflect precisely
        what is on the $PATH.
        """
        return len(self._cmds_cache)

    def lazyget(self, key, default=None):
        """A lazy value getter."""
        return self._cmds_cache.get(self.cached_name(key), default)

    def locate_binary(self, name, ignore_alias=False):
        """Locates an executable on the file system using the cache.

        NOT RECOMMENDED. Take a look into `xonsh.procs.executables.locate_executable`
        before using this function.

        Parameters
        ----------
        name : str
            name of binary to search for
        ignore_alias : bool, optional
            Force return of binary path even if alias of ``name`` exists
            (default ``False``)
        """
        self.update_cache()
        return self.lazy_locate_binary(name, ignore_alias)

    def lazy_locate_binary(self, name, ignore_alias=False):
        """Locates an executable in the cache, without checking its validity.

        NOT RECOMMENDED. Take a look into `xonsh.procs.executables.locate_executable`
        before using this function.

        Parameters
        ----------
        name : str
            name of binary to search for
        ignore_alias : bool, optional
            Force return of binary path even if alias of ``name`` exists
            (default ``False``)
        """
        possibilities = self.get_possible_names(name)
        cached = next((cmd for cmd in possibilities if cmd in self._cmds_cache), None)
        if cached:
            (path, alias) = self._cmds_cache[cached]
            ispure = path == pathbasename(path)
            if alias and ignore_alias and ispure:
                # pure alias, which we are ignoring
                return None
            else:
                return path
        elif os.path.isfile(name) and name != pathbasename(name):
            return name

    def is_only_functional_alias(self, name):
        """Returns whether or not a command is only a functional alias, and has
        no underlying executable. For example, the "cd" command is only available
        as a functional alias.
        """
        self.update_cache()
        return self.lazy_is_only_functional_alias(name)

    def lazy_is_only_functional_alias(self, name) -> bool:
        """Returns whether or not a command is only a functional alias, and has
        no underlying executable. For example, the "cd" command is only available
        as a functional alias. This search is performed lazily.
        """
        val = self._cmds_cache.get(name, None)
        if val is None:
            return False
        return (
            val == (name, True) and self.locate_binary(name, ignore_alias=True) is None
        )

    def predict_threadable(self, cmd):
        """Predicts whether a command list is able to be run on a background
        thread, rather than the main thread.
        """
        predictor = self.get_predictor_threadable(cmd[0])
        return predictor(cmd[1:], self)

    def get_predictor_threadable(self, cmd0):
        """Return the predictor whether a command list is able to be run on a
        background thread, rather than the main thread.
        """
        name = self.cached_name(cmd0)
        predictors = self.threadable_predictors
        if name not in predictors:
            predictors[name] = self.default_predictor(name, cmd0)
        predictor = predictors[name]
        return predictor

    #
    # Background Predictors (as methods)
    #

    def default_predictor(self, name, cmd0):
        """Default predictor, using predictor from original command if the
        command is an alias, elseif build a predictor based on binary analysis
        on POSIX, else return predict_true.
        """
        # alias stuff
        if not os.path.isabs(cmd0) and os.sep not in cmd0:
            if cmd0 in self.aliases:
                return self.default_predictor_alias(cmd0)

        # other default stuff
        if ON_POSIX:
            return self.default_predictor_readbin(
                name, cmd0, timeout=0.1, failure=predict_true
            )
        else:
            return predict_true

    def default_predictor_alias(self, cmd0):
        alias_recursion_limit = (
            10  # this limit is se to handle infinite loops in aliases definition
        )
        first_args = []  # contains in reverse order args passed to the aliased command
        while cmd0 in self.aliases:
            alias_name = self.aliases
            if isinstance(alias_name, (str, bytes)) or not isinstance(
                alias_name, cabc.Sequence
            ):
                return predict_true
            for arg in alias_name[:0:-1]:
                first_args.insert(0, arg)
            if cmd0 == alias_name[0]:
                # it is a self-alias stop recursion immediatly
                return predict_true
            cmd0 = alias_name[0]
            alias_recursion_limit -= 1
            if alias_recursion_limit == 0:
                return predict_true
        predictor_cmd0 = self.get_predictor_threadable(cmd0)
        return lambda cmd1: predictor_cmd0(first_args[::-1] + cmd1, self)

    def default_predictor_readbin(self, name, cmd0, timeout, failure):
        """Make a default predictor by
        analyzing the content of the binary. Should only works on POSIX.
        Return failure if the analysis fails.
        """
        fname = cmd0 if os.path.isabs(cmd0) else None
        fname = cmd0 if fname is None and os.sep in cmd0 else fname
        fname = self.lazy_locate_binary(name) if fname is None else fname

        if fname is None:
            return failure
        if not os.path.isfile(fname):
            return failure
        if (link := self.resolve_symlink(fname)) and link.endswith("coreutils"):
            """
            On NixOS the core tools are the symlinks to one universal ``coreutils`` binary file.
            Detect it and use the default mode.
            """
            return failure

        try:
            fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
        except Exception:
            return failure  # opening error

        search_for = {
            (b"ncurses",): [False],
            (b"libgpm",): [False],
            (b"isatty", b"tcgetattr", b"tcsetattr"): [False, False, False],
        }
        tstart = time.time()
        block = b""
        while time.time() < tstart + timeout:
            previous_block = block
            try:
                block = os.read(fd, 2048)
            except Exception:
                # should not occur, except e.g. if a file is deleted a a dir is
                # created with the same name between os.path.isfile and os.open
                os.close(fd)
                return failure
            if len(block) == 0:
                os.close(fd)
                return predict_true  # no keys of search_for found
            analyzed_block = previous_block + block
            for k, v in search_for.items():
                for i in range(len(k)):
                    if v[i]:
                        continue
                    if k[i] in analyzed_block:
                        v[i] = True
                if all(v):
                    os.close(fd)
                    return predict_false  # use one key of search_for
        os.close(fd)
        return failure  # timeout


#
# Background Predictors
#


def predict_true(_, __):
    """Always say the process is threadable."""
    return True


def predict_false(_, __):
    """Never say the process is threadable."""
    return False


@lazyobject
def SHELL_PREDICTOR_PARSER():
    p = argparse.ArgumentParser("shell", add_help=False)
    p.add_argument("-c", nargs="?", default=None)
    p.add_argument("filename", nargs="?", default=None)
    return p


def predict_shell(args, _):
    """Predict the backgroundability of the normal shell interface, which
    comes down to whether it is being run in subproc mode.
    """
    ns, _ = SHELL_PREDICTOR_PARSER.parse_known_args(args)
    if ns.c is None and ns.filename is None:
        pred = False
    else:
        pred = True
    return pred


@lazyobject
def HELP_VER_PREDICTOR_PARSER():
    p = argparse.ArgumentParser("cmd", add_help=False)
    p.add_argument("-h", "--help", dest="help", nargs="?", action="store", default=None)
    p.add_argument(
        "-v", "-V", "--version", dest="version", nargs="?", action="store", default=None
    )
    return p


def predict_help_ver(args, _):
    """Predict the backgroundability of commands that have help & version
    switches: -h, --help, -v, -V, --version. If either of these options is
    present, the command is assumed to print to stdout normally and is therefore
    threadable. Otherwise, the command is assumed to not be threadable.
    This is useful for commands, like top, that normally enter alternate mode
    but may not in certain circumstances.
    """
    ns, _ = HELP_VER_PREDICTOR_PARSER.parse_known_args(args)
    pred = ns.help is not None or ns.version is not None
    return pred


@lazyobject
def HG_PREDICTOR_PARSER():
    p = argparse.ArgumentParser("hg", add_help=False)
    p.add_argument("command")
    p.add_argument(
        "-i", "--interactive", action="store_true", default=False, dest="interactive"
    )
    return p


def predict_hg(args, _):
    """Predict if mercurial is about to be run in interactive mode.
    If it is interactive, predict False. If it isn't, predict True.
    Also predict False for certain commands, such as split.
    """
    ns, _ = HG_PREDICTOR_PARSER.parse_known_args(args)
    if ns.command == "split":
        return False
    else:
        return not ns.interactive


def predict_env(args, cmd_cache: CommandsCache):
    """Predict if env is launching a threadable command or not.
    The launched command is extracted from env args, and the predictor of
    lauched command is used."""

    for i in range(len(args)):
        if args[i] and args[i][0] != "-" and "=" not in args[i]:
            # args[i] is the command and the following is its arguments
            # so args[i:] is used to predict if the command is threadable
            return cmd_cache.predict_threadable(args[i:])
    return True


def default_threadable_predictors():
    """Generates a new defaultdict for known threadable predictors.
    The default is to predict true.
    """
    # alphabetical, for what it is worth.
    predictors = {
        "asciinema": predict_help_ver,
        "aurman": predict_false,
        "awk": predict_true,
        "bash": predict_shell,
        "cat": predict_false,
        "clear": predict_false,
        "cls": predict_false,
        "cmd": predict_shell,
        "cryptop": predict_false,
        "cryptsetup": predict_true,
        "csh": predict_shell,
        "curl": predict_true,
        "elvish": predict_shell,
        "emacsclient": predict_false,
        "env": predict_env,
        "ex": predict_false,
        "fish": predict_shell,
        "gawk": predict_true,
        "ghci": predict_help_ver,
        "git": predict_true,
        "gvim": predict_help_ver,
        "hg": predict_hg,
        "htop": predict_help_ver,
        "ipython": predict_shell,
        "julia": predict_shell,
        "ksh": predict_shell,
        "less": predict_help_ver,
        "ls": predict_true,
        "man": predict_help_ver,
        "mc": predict_false,
        "more": predict_help_ver,
        "mutt": predict_help_ver,
        "mvim": predict_help_ver,
        "nano": predict_help_ver,
        "nmcli": predict_true,
        "nvim": predict_false,
        "percol": predict_false,
        "ponysay": predict_help_ver,
        "psql": predict_false,
        "push": predict_shell,
        "pv": predict_false,
        "python": predict_shell,
        "python2": predict_shell,
        "python3": predict_shell,
        "ranger": predict_help_ver,
        "repo": predict_help_ver,
        "rview": predict_false,
        "rvim": predict_false,
        "rwt": predict_shell,
        "scp": predict_false,
        "sh": predict_shell,
        "ssh": predict_false,
        "startx": predict_false,
        "sudo": predict_help_ver,
        "sudoedit": predict_help_ver,
        "systemctl": predict_true,
        "tcsh": predict_shell,
        "telnet": predict_false,
        "top": predict_help_ver,
        "tput": predict_false,
        "udisksctl": predict_true,
        "unzip": predict_true,
        "vi": predict_false,
        "view": predict_false,
        "vim": predict_false,
        "vimpager": predict_help_ver,
        "weechat": predict_help_ver,
        "wget": predict_true,
        "xclip": predict_help_ver,
        "xdg-open": predict_false,
        "xo": predict_help_ver,
        "xon.sh": predict_shell,
        "xonsh": predict_shell,
        "yes": predict_false,
        "zip": predict_true,
        "zipinfo": predict_true,
        "zsh": predict_shell,
    }
    return predictors
