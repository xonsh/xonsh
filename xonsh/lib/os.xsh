"""Xonsh extension of the standard library os module, using xonsh for
subprocess calls"""
from contextlib import contextmanager


@contextmanager
def indir(d):
    """Context manager for temporarily entering into a directory."""
    ![pushd @(d)]
    yield
    ![popd]
