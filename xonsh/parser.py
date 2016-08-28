# -*- coding: utf-8 -*-
"""Implements the xonsh parser."""
from xonsh.lazyasd import lazyobject


def PythonParser():
    from xonsh.platform import PYTHON_VERSION_INFO
    if PYTHON_VERSION_INFO < (3, 5, 0):
        from xonsh.parsers.v34 import Parser as p
    else:
        from xonsh.parsers.v35 import Parser as p
    return p


@lazyobject
def Parser():
    from xonsh.parsers.subproc import SubprocParser
    return type('Parser', (PythonParser(), SubprocParser), {})
