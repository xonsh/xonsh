# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.4."""
import os
import sys
from collections import Iterable, Sequence, Mapping

from xonsh import ast
from xonsh.lexer import LexToken
from xonsh.parsers.base import BaseParser, xonsh_help, xonsh_superhelp

class Parser(BaseParser):
    """A Python v3.4 compliant parser for the xonsh language."""

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
        opt_rules = ['argument_comma_list', 'comma_argument_list',]
        for rule in opt_rules:
            self._opt_rule(rule)

        list_rules = ['argument_comma',]
        for rule in list_rules:
            self._list_rule(rule)

        super().__init__(lexer_optimize=lexer_optimize, lexer_table=lexer_table,
                 yacc_optimize=yacc_optimize, yacc_table=yacc_table, 
                 yacc_debug=yacc_debug, outputdir=outputdir)

    def p_classdef_or_funcdef(self, p):
        """classdef_or_funcdef : classdef
                               | funcdef
        """
        p[0] = p[1]

    def p_atom_expr(self, p):
        """atom_expr : atom trailer_list_opt"""
        leader, trailers = p[1], p[2]
        p0 = leader
        if trailers is None:
            trailers = []
        for trailer in trailers:
            if isinstance(trailer, (ast.Index, ast.Slice)):
                p0 = ast.Subscript(value=leader,
                                   slice=trailer,
                                   ctx=ast.Load(),
                                   lineno=leader.lineno,
                                   col_offset=leader.col_offset)
            elif isinstance(trailer, Mapping):
                p0 = ast.Call(func=leader,
                              lineno=leader.lineno,
                              col_offset=leader.col_offset, **trailer)
            elif isinstance(trailer, str):
                if trailer == '?':
                    p0 = xonsh_help(leader, lineno=leader.lineno, 
                                    col=leader.col_offset)
                elif trailer == '??':
                    p0 = xonsh_superhelp(leader,
                                         lineno=leader.lineno,
                                         col=leader.col_offset)
                else:
                    p0 = ast.Attribute(value=leader,
                                       attr=trailer,
                                       ctx=ast.Load(),
                                       lineno=leader.lineno,
                                       col_offset=leader.col_offset)
            else:
                assert False
            leader = p0
        p[0] = p0

    def p_item(self, p):
        """item : test COLON test"""
        lenp = len(p)
        if lenp == 4:
            p0 = [p[1], p[3]]
        elif lenp == 3:
            p0 = [None, p[2]]
        else:
            assert False
        p[0] = p0
