# -*- coding: utf-8 -*-
"""Module for caching command & alias names as well as for predicting whether
a command will be able to be run in the background.

A background predictor is a function that accepts a single argument list
and returns whether or not the process can be run in the background (returns
True) or must be run the foreground (returns False).
"""
import os
import time
import builtins
import argparse
import collections.abc as cabc

from xonsh.platform import ON_WINDOWS, ON_POSIX, pathbasename
from xonsh.tools import executables_in, print_warning
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
        self._threadable_predictors = {}

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

    @property
    def threadable_predictors(self):
        print_warning("CommandsCache.threadable_predictors has been deprecated "
                      "because it is no longer needed. Please remove downstream "
                      "references to it. These operations will have no effect.")
        return self._threadable_predictors

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
        for e in p:
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
        cache_valid = path_hash == self._path_checksum
        self._path_checksum = path_hash
        # did aliases change?
        alss = getattr(builtins, "aliases", dict())
        al_hash = hash(frozenset(alss))
        cache_valid = cache_valid and al_hash == self._alias_checksum
        self._alias_checksum = al_hash
        # did the contents of any directory in PATH change?
        max_mtime = 0
        for path in path_immut:
            mtime = os.stat(path).st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
        cache_valid = cache_valid and (max_mtime <= self._path_mtime)
        self._path_mtime = max_mtime
        if cache_valid:
            return self._cmds_cache
        allcmds = {}
        for path in reversed(path_immut):
            # iterate backwards so that entries at the front of PATH overwrite
            # entries at the back.
            for cmd in executables_in(path):
                key = cmd.upper() if ON_WINDOWS else cmd
                allcmds[key] = (os.path.join(path, cmd), alss.get(key, None))
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
