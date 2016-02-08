# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.5."""
import os
import sys
from collections import Iterable, Sequence, Mapping

from xonsh import ast
from xonsh.lexer import LexToken
from xonsh.parsers.base import BaseParser, xonsh_help, xonsh_superhelp

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

    def p_atom_expr(self, p):
        """atom_expr : atom trailer_list_opt
                     | await_tok atom trailer_list_opt
        """
        lenp = len(p)
        if lenp == 3:
            leader, trailers = p[1], p[2]
        elif lenp == 4:
            leader, trailers = p[2], p[3]
        else:
            assert False
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
        if lenp == 4:
            p1 = p[1]
            p0 = ast.Await(value=p0, ctx=ast.Load(), lineno=p1.lineno,
                           col_offset=p1.lexpos)
        p[0] = p0

    def p_async_stmt(self, p):
        """async_stmt : async_funcdef
                      | async_with_stmt
                      | async_for_stmt
        """
        p[0] = p[1]

    def p_item(self, p):
        """item : test COLON test
                | POW expr
        """
        lenp = len(p)
        if lenp == 4:
            p0 = [p[1], p[3]]
        elif lenp == 3:
            p0 = [None, p[2]]
        else:
            assert False
        p[0] = p0

    def p_arglist(self, p):
        """arglist : argument comma_opt
                   | argument comma_argument_list comma_opt
        """
        p0 = {'args': [], 'keywords': []}
        p1, p2 = p[1], p[2]
        p2 = None if p2 == ',' else p2
        self._set_arg(p0, p1)
        if p2 is not None:
            for arg in p2:
                self._set_arg(p0, arg)
        p[0] = p0

    def p_argument(self, p):
        """argument : test_or_star_expr
                    | test comp_for
                    | test EQUALS test
                    | POW test
                    | TIMES test
        """
        # "test '=' test" is really "keyword '=' test", but we have no such token.
        # These need to be in a single rule to avoid grammar that is ambiguous
        # to our LL(1) parser. Even though 'test' includes '*expr' in star_expr,
        # we explicitly match '*' here, too, to give it proper precedence.
        # Illegal combinations and orderings are blocked in ast.c:
        # multiple (test comp_for) arguements are blocked; keyword unpackings
        # that precede iterable unpackings are blocked; etc.
        p1 = p[1]
        lenp = len(p)
        if lenp == 2:
            p0 = p1
        elif lenp == 3:
            if p1 == '**':
                p0 = ast.keyword(arg=None, value=p[2])
            elif p1 == '*':
                p0 = ast.Starred(value=p[2])
            else:
                p0 = ast.GeneratorExp(elt=p1, generators=p[2]['comps'],
                                      lineno=p1.lineno, col_offset=p1.col_offset)
        elif lenp == 4:
            p0 = ast.keyword(arg=p1.id, value=p[3])
        else:
            assert False
        p[0] = p0
