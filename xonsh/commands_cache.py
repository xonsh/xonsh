# -*- coding: utf-8 -*-
"""Module for caching command & alias names as well as for predicting whether
a command will be able to be run in the background.

A background predictor is a function that accepts a single argument list
and returns whether or not the process can be run in the background (returns
True) or must be run the foreground (returns False).
"""
import os
import sys
import time
import builtins
import argparse
import collections.abc as cabc

from xonsh.platform import ON_WINDOWS, ON_POSIX, pathbasename
from xonsh.tools import executables_in
from xonsh.lazyasd import lazyobject


class CommandsCache(cabc.Mapping):
    """A lazy cache representing the commands available on the file system.
    The keys are the command names and the values a tuple of (loc, has_alias)
    where loc is either a str pointing to the executable on the file system or
    None (if no executable exists) and has_alias is a boolean flag for whether
    the command has an alias.
    """

    def __init__(self):
        self._cmds_cache = {}
        self._path_checksum = None
        self._alias_checksum = None
        self._path_mtime = -1
        self.threadable_predictors = default_threadable_predictors()

    def __contains__(self, key):
        _ = self.all_commands
        return self.lazyin(key)

    def __iter__(self):
        for cmd, (path, is_alias) in self.all_commands.items():
            if ON_WINDOWS and path is not None:
                # All command keys are stored in uppercase on Windows.
                # This ensures the original command name is returned.
                cmd = pathbasename(path)
            yield cmd

    def __len__(self):
        return len(self.all_commands)

    def __getitem__(self, key):
        _ = self.all_commands
        return self.lazyget(key)

    def is_empty(self):
        """Returns whether the cache is populated or not."""
        return len(self._cmds_cache) == 0

    @staticmethod
    def get_possible_names(name):
        """Generates the possible `PATHEXT` extension variants of a given executable
        name on Windows as a list, conserving the ordering in `PATHEXT`.
        Returns a list as `name` being the only item in it on other platforms."""
        if ON_WINDOWS:
            pathext = builtins.__xonsh__.env.get("PATHEXT", [])
            name = name.upper()
            return [name + ext for ext in ([""] + pathext)]
        else:
            return [name]

    @staticmethod
    def remove_dups(p):
        ret = list()
        for e in map(os.path.realpath, p):
            if e not in ret:
                ret.append(e)
        return ret

    @property
    def all_commands(self):
        paths = builtins.__xonsh__.env.get("PATH", [])
        paths = CommandsCache.remove_dups(paths)
        path_immut = tuple(x for x in paths if os.path.isdir(x))
        # did PATH change?
        path_hash = hash(path_immut)
        cache_valid_path = path_hash == self._path_checksum
        self._path_checksum = path_hash
        # did aliases change?
        alss = getattr(builtins, "aliases", dict())
        al_hash = hash(frozenset(alss))
        cache_valid_aliases = al_hash == self._alias_checksum
        self._alias_checksum = al_hash
        # did the contents of any directory in PATH change?
        max_mtime = 0
        for path in path_immut:
            mtime = os.stat(path).st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
        cache_valid_paths = max_mtime <= self._path_mtime
        self._path_mtime = max_mtime

        if cache_valid_path and cache_valid_paths:
            if not cache_valid_aliases:
                for cmd, alias in alss.items():
                    key = cmd.upper() if ON_WINDOWS else cmd
                    if key in self._cmds_cache:
                        self._cmds_cache[key] = (self._cmds_cache[key][0], alias)
                    else:
                        self._cmds_cache[key] = (cmd, True)
            return self._cmds_cache

        allcmds = {}
        for path in reversed(path_immut):
            # iterate backwards so that entries at the front of PATH overwrite
            # entries at the back.
            for cmd in executables_in(path):
                key = cmd.upper() if ON_WINDOWS else cmd
                allcmds[key] = (os.path.join(path, cmd), alss.get(key, None))

        warn_cnt = builtins.__xonsh__.env.get("COMMANDS_CACHE_SIZE_WARNING")
        if warn_cnt and len(allcmds) > warn_cnt:
            print(
                f"Warning! Found {len(allcmds):,} executable files in the PATH directories!",
                file=sys.stderr,
            )

        for cmd in alss:
            if cmd not in allcmds:
                key = cmd.upper() if ON_WINDOWS else cmd
                allcmds[key] = (cmd, True)

        self._cmds_cache = allcmds
        return allcmds

    def cached_name(self, name):
        """Returns the name that would appear in the cache, if it exists."""
        if name is None:
            return None
        cached = pathbasename(name)
        if ON_WINDOWS:
            keys = self.get_possible_names(cached)
            cached = next((k for k in keys if k in self._cmds_cache), None)
        return cached

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

        Parameters
        ----------
        name : str
                name of binary to search for
        ignore_alias : bool, optional
                Force return of binary path even if alias of ``name`` exists
                (default ``False``)
        """
        # make sure the cache is up to date by accessing the property
        _ = self.all_commands
        return self.lazy_locate_binary(name, ignore_alias)

    def lazy_locate_binary(self, name, ignore_alias=False):
        """Locates an executable in the cache, without checking its validity.

        Parameters
        ----------
        name : str
                name of binary to search for
        ignore_alias : bool, optional
                Force return of binary path even if alias of ``name`` exists
                (default ``False``)
        """
        possibilities = self.get_possible_names(name)
        if ON_WINDOWS:
            # Windows users expect to be able to execute files in the same
            # directory without `./`
            local_bin = next((fn for fn in possibilities if os.path.isfile(fn)), None)
            if local_bin:
                return os.path.abspath(local_bin)
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
        _ = self.all_commands
        return self.lazy_is_only_functional_alias(name)

    def lazy_is_only_functional_alias(self, name):
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
        return predictor(cmd[1:])

    def get_predictor_threadable(self, cmd0):
        """Return the predictor whether a command list is able to be run on a
        background thread, rather than the main thread.
        """
        name = self.cached_name(cmd0)
        predictors = self.threadable_predictors
        if ON_WINDOWS:
            # On all names (keys) are stored in upper case so instead
            # we get the original cmd or alias name
            path, _ = self.lazyget(name, (None, None))
            if path is None:
                return predict_true
            else:
                name = pathbasename(path)
            if name not in predictors:
                pre, ext = os.path.splitext(name)
                if pre in predictors:
                    predictors[name] = predictors[pre]
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
            alss = getattr(builtins, "aliases", dict())
            if cmd0 in alss:
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
        alss = getattr(builtins, "aliases", dict())
        while cmd0 in alss:
            alias_name = alss[cmd0]
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
        return lambda cmd1: predictor_cmd0(first_args[::-1] + cmd1)

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


def predict_true(args):
    """Always say the process is threadable."""
    return True


def predict_false(args):
    """Never say the process is threadable."""
    return False


@lazyobject
def SHELL_PREDICTOR_PARSER():
    p = argparse.ArgumentParser("shell", add_help=False)
    p.add_argument("-c", nargs="?", default=None)
    p.add_argument("filename", nargs="?", default=None)
    return p


def predict_shell(args):
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


def predict_help_ver(args):
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


def predict_hg(args):
    """Predict if mercurial is about to be run in interactive mode.
    If it is interactive, predict False. If it isn't, predict True.
    Also predict False for certain commands, such as split.
    """
    ns, _ = HG_PREDICTOR_PARSER.parse_known_args(args)
    if ns.command == "split":
        return False
    else:
        return not ns.interactive


def predict_env(args):
    """Predict if env is launching a threadable command or not.
    The launched command is extracted from env args, and the predictor of
    lauched command is used."""

    for i in range(len(args)):
        if args[i] and args[i][0] != "-" and "=" not in args[i]:
            # args[i] is the command and the following is its arguments
            # so args[i:] is used to predict if the command is threadable
            return builtins.__xonsh__.commands_cache.predict_threadable(args[i:])
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
