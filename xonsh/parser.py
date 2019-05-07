# -*- coding: utf-8 -*-
"""Implements the xonsh parser."""
from xonsh.lazyasd import lazyobject
from xonsh.platform import PYTHON_VERSION_INFO


@lazyobject
def Parser():
    if PYTHON_VERSION_INFO > (3, 6):
        from xonsh.parsers.v36 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 5):
        from xonsh.parsers.v35 import Parser as p
    return p
