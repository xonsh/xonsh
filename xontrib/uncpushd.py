"""Utilities for handling UNC (\\node\share\...) paths in PUSHD (on Windows)"""

from xonsh.dirstack import DIRSTACK, pushd, popd

def unc_pushd( args, stdin=None):
    """Handle pushd when argument is a UNC path. (\\<server>\<share>...)
    Currently, a no-op, till I figure out what exactly to do.
    """
    return None, 'Welcome to the Monkey House', 0
    pass
