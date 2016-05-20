# -*- coding: utf-8 -*-
"""Implements the xonsh parser."""
from xonsh.platform import PYTHON_VERSION_INFO

if PYTHON_VERSION_INFO < (3, 5, 0):
    from xonsh.parsers.v34 import Parser
else:
    from xonsh.parsers.v35 import Parser
