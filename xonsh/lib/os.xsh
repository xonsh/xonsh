"""Xonsh extension of the standard library os module, using xonsh for
subprocess calls"""
import sys

from xonsh.imphooks import XonshImportHook

sys.meta_path.append(XonshImportHook())

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
