# -*- coding: utf-8 -*-
"""Implements the xonsh parser."""
from xonsh.tools import (VER_3_4, VER_3_5, VER_MAJOR_MINOR)

if VER_MAJOR_MINOR <= VER_3_4:
    from xonsh.parsers.v34 import Parser
else:
    from xonsh.parsers.v35 import Parser
