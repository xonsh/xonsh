import os
from contextlib import contextmanager


@contextmanager
def indir(d):
    """Context manager for temporarily entering into a directory.
     Copyright (c) 2017, Anthony Scopatz
     Copyright (c) 2018, The Regro Developers"""
    old_d = os.getcwd()
    ![cd @(d)]
    yield
    ![cd @(old_d)]


def run(cmd, cwd=None, check=False):
    """Stub for ``subprocess.run`` like functionality"""
    if cwd is None:
        cwd = '.'
    with indir(cwd), ${...}.swap(RAISE_SUBPROC_ERROR=check):
        ![@(cmd)]

def check_call(cmd, cwd=None):
    """Stub for ``subprocess.check_call`` like functionality"""
    run(cmd, cwd=cwd, check=True)
