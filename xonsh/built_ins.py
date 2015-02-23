"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import builtins
import subprocess
from glob import glob, iglob
from contextlib import contextmanager
from collections import MutableMapping, Iterable

from xonsh.tools import string_types

BUILTINS_LOADED = False
ENV = None

class Env(MutableMapping):
    """A xonsh environment, whose variables have limited typing 
    (unlike BASH). Most variables are, by default, strings (like BASH).
    However, the following rules also apply based on variable-name:

    * PATH: any variable whose name ends in PATH is a list of strings.

    An Env instance may be converted to an untyped version suitable for 
    use in a subprocess.
    """

    def __init__(self, *args, **kwargs):
        """If no initial environment is given, os.environ is used."""
        self._d = {}
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ,)
        for key, val in dict(*args, **kwargs).items():
            self[key] = val
        self._detyped = None

    def detype(self):
        if self._detyped is not None:
            return self._detyped
        ctx = {}
        for key, val in self._d.items():
            if not isinstance(key, string_types):
                key = str(key)
            if 'PATH' in key:
                val = os.pathsep.join(val)
            elif not isinstance(val, string_types):
                val = str(val)
            ctx[key] = val
        self._detyped = ctx
        return ctx

    def replace_env(self):
        """Replaces the contents of os.environ with a detyped version 
        of the xonsh environement.
        """
        os.environ.clear()
        os.environ.update(self.detype())

    #
    # Mutable mapping interface
    #

    def __getitem__(self, key):
        return self._d[key]

    def __setitem__(self, key, val):
        if isinstance(key, string_types) and 'PATH' in key:
            val = val.split(os.pathsep) if isinstance(val, string_types) \
                  else val
        self._d[key] = val
        self._detyped = None
        
    def __delitem__(self, key):
        del self._d[key]
        self._detyped = None

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__class__.__module__, 
                                     self.__class__.__name__, self._d)

def helper(x):
    """Prints help about, and then returns that variable."""
    
    return x


def _partsjoin(parts):
    s = os.path.join(parts)
    if len(parts[0]) == 0:
        s = os.sep + s  # fix for root dir
    return s


def reglob(path, parts=None, i=None):
    """Regular expression-based globbing."""
    if parts is None:
        parts = path.split(os.sep)
        d = os.sep if path.startswith(os.sep) else '.'
        return reglob(d, parts=parts, i=0)
    base = subdir = path
    if i == 0 and base == '.':
        base = ''
    regex = re.compile(os.path.join(base, parts[i]))
    files = os.listdir(subdir)
    files.sort()
    paths = []
    i1 = i + 1
    if i1 == len(parts):
        for f in files: 
            p = os.path.join(base, f)
            if regex.match(p) is not None:
                paths.append(p)
    else:
        for f in files: 
            p = os.path.join(base, f)
            if regex.match(p) is None or not os.path.isdir(p):
                continue
            paths += reglob(p, parts=parts, i=i1)
    return paths


def regexpath(s):
    """Takes a regular expression string and returns a list of file
    paths that match the regex.
    """
    global ENV
    if ENV is not None:
        ENV.replace_env()
    s = os.path.expanduser(s)
    s = os.path.expandvars(s)
    return reglob(s)


def load_builtins():
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED, ENV
    builtins.__xonsh_env__ = ENV = Env()
    builtins.__xonsh_help__ = helper
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = regexpath
    builtins.__xonsh_subproc__ = subprocess
    BUILTINS_LOADED = True

def unload_builtins():
    """Removes the xonsh builtins from the Python builins, if the 
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED, ENV
    if ENV is not None:
        ENV = None
    if not BUILTINS_LOADED:
        return
    del (builtins.__xonsh_env__,
         builtins.__xonsh_help__,
         builtins.__xonsh_superhelp__,
         builtins.__xonsh_regexpath__,
         builtins.__xonsh_subproc__,
         )
    BUILTINS_LOADED = False

@contextmanager
def xonsh_builtins():
    """A context manager for using the xonsh builtins only in a limited
    scope. Likely useful in testing.
    """
    load_builtins()
    yield
    unload_builtins()


