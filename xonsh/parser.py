"""Implements the xonsh parser."""

import os

from xonsh.lib.lazyasd import lazyobject
from xonsh.platform import PYTHON_VERSION_INFO


@lazyobject
def Parser():
    if os.environ.get("XONSH_RD_PARSER"):
        from xonsh.parsers.rd_parser import Parser as p
    elif PYTHON_VERSION_INFO >= (3, 13):
        from xonsh.parsers.v313 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 10):
        from xonsh.parsers.v310 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 9):
        from xonsh.parsers.v39 import Parser as p
    elif PYTHON_VERSION_INFO > (3, 8):
        from xonsh.parsers.v38 import Parser as p
    else:
        from xonsh.parsers.v36 import Parser as p
    return p
