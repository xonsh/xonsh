"""Xonsh extension of the standard library os module, using xonsh for
subprocess calls

Originally posted in https://github.com/xonsh/xonsh/issues/2726#issuecomment-406447196 :
    Recently @CJ-Wright has started up a ``xonsh.lib`` sub-package, which is usable from pure Python.
    This is meant as a standard library for xonsh and downstream tools.
    Currently there are some xonsh-ish wrappers around ``os`` and ``subprocess``.
    We'd love to see more contributions to this effort! So if there is something
    like ``sh()`` that you'd like to see, by all means please help us add it!
"""

import sys

from xonsh.built_ins import subproc_uncaptured
from xonsh.dirstack import with_pushd

indir = with_pushd
"""alias to push_d context manager"""


def rmtree(dirname, force=False):
    """Remove a directory, even if it has read-only files (Windows).
    Git creates read-only files that must be removed on teardown. See
    https://stackoverflow.com/questions/2656322  for more info.

    Parameters
    ----------
    dirname : str
        Directory to be removed
    force : bool
        If True force removal, defaults to False
    """
    if sys.platform == "win32":
        cmd_args = "/S/Q"
        subproc_uncaptured(["rmdir", cmd_args, dirname])
    else:
        cmd_args = "-r"
        if force:
            cmd_args += "f"
        subproc_uncaptured(["rm", cmd_args, dirname])
