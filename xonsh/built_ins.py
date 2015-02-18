"""The xonsh built-ins. Note that this module is named 'built_ins' so as
not to be confused with the special Python builtins module.
"""
import os
import builtins
import subprocess
from contextlib import contextmanager
from collections import MutableMapping

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
        if len(args) == 0 and len(kwargs) == 0:
            args = (os.environ,)
        super(Env, self).__init__(*args, **kwargs)

    def detype():
        pass


def load_builtins():
    """Loads the xonsh builtins into the Python builtins. Sets the
    BUILTINS_LOADED variable to True.
    """
    global BUILTINS_LOADED
    builtins.__xonsh_env__ = {}
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


