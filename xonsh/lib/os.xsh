"""Xonsh extension of the standard library os module, using xonsh for
subprocess calls"""
from contextlib import contextmanager


@contextmanager
def indir(d):
    """Context manager for temporarily entering into a directory."""
    ![pushd @(d)]
    yield
    ![popd]


def rmtree(dirname):
    """Remove a directory, even if it has read-only files (Windows).
    Git creates read-only files that must be removed on teardown. See
    https://stackoverflow.com/questions/2656322  for more info.

    Parameters
    ----------
    dirname : str
        Directory to be removed
    """
    try:
        rm -r @(dirname)
    except PermissionError:
        if sys.platform == "win32":
            from xonsh.lib import subprocess
            subprocess.check_call(["del", "/F/S/Q", dirname])
        else:
            raise
