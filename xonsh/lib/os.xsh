"""Xonsh extension of the standard library os module, using xonsh for
subprocess calls"""
from contextlib import contextmanager
import sys


@contextmanager
def indir(d):
    """Context manager for temporarily entering into a directory."""
    ![pushd @(d)]
    try:
        yield
    finally:
        ![popd]


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
    cmd_args = '-r'
    if force:
        cmd_args += 'f'
    try:
        ![rm @(cmd_args) @(dirname)]
    except PermissionError:
        if sys.platform == "win32":
            ![del /F/S/Q @(dirname)]
        else:
            raise
