# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.5."""
import os
import sys
from collections import Iterable, Sequence, Mapping

from xonsh import ast
from xonsh.lexer import LexToken
from xonsh.parsers.base import BaseParser

class Parser(BaseParser):
    """A Python v3.5 compliant parser for the xonsh language."""

    def __init__(self, lexer_optimize=True, lexer_table='xonsh.lexer_table',
                 yacc_optimize=True, yacc_table='xonsh.parser_table', 
                 yacc_debug=False, outputdir=None):
        """Parameters
        ----------
        lexer_optimize : bool, optional
            Set to false when unstable and true when lexer is stable.
        lexer_table : str, optional
            Lexer module used when optimized.
        yacc_optimize : bool, optional
            Set to false when unstable and true when parser is stable.
        yacc_table : str, optional
            Parser module used when optimized.
        yacc_debug : debug, optional
            Dumps extra debug info.
        outputdir : str or None, optional
            The directory to place generated tables within.
        """
        # Rule creation and modifiation *must* take place before super()
        super().__init__(lexer_optimize=lexer_optimize, lexer_table=lexer_table,
                 yacc_optimize=yacc_optimize, yacc_table=yacc_table, 
                 yacc_debug=yacc_debug, outputdir=outputdir)

    def p_classdef_or_funcdef(self, p):
        """classdef_or_funcdef : classdef
                               | funcdef
                               | async_funcdef
        """
        p[0] = p[1]
