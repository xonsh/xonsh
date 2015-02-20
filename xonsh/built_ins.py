"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import builtins
import subprocess
from contextlib import contextmanager
from collections import MutableMapping, Iterable

from xonsh.tools import string_types

BUILTINS_LOADED = False

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

    def detype(self):
        ctx = {}
        for key, val in self._d.items():
            if not isinstance(key, string_types):
                key = str(key)
            if 'PATH' in key:
                val = os.pathsep.join(val)
            elif not isinstance(val, string_types):
                val = str(val)
            ctx[key] = val
        return ctx

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
        
    def __delitem__(self, key):
        del self._d[key]

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)

    def __str__(self):
        return str(self._d)

    def __repr__(self):
        return '{0}.{1}({2})'.format(self.__class__.__module__, 
                                     self.__class__.__name__, self._d)

def xonsh_help(x):
    """A variable to print help about, and then return."""
    
    return x


def load_builtins():
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED
    builtins.__xonsh_env__ = Env()
    builtins.__xonsh_help__ = lambda x: x
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_subproc__ = subprocess
    BUILTINS_LOADED = True

def unload_builtins():
    """Removes the xonsh builtins from the Python builins, if the 
    BUILTINS_LOADED is True, sets BUILTINS_LOADED to False, and returns.
    """
    global BUILTINS_LOADED
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


