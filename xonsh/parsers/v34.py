# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.4."""
import os
import sys
from collections import Iterable, Sequence, Mapping

from xonsh import ast
from xonsh.lexer import LexToken
from xonsh.parsers.base import BaseParser

class Parser(BaseParser):
    """A Python v3.4 compliant parser for the xonsh language."""
