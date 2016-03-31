# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.4."""
from xonsh import ast
from xonsh.parsers.base import BaseParser


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
        opt_rules = ['argument_comma_list', 'comma_argument_list']
        for rule in opt_rules:
            self._opt_rule(rule)

        list_rules = ['argument_comma']
        for rule in list_rules:
            self._list_rule(rule)

        super().__init__(lexer_optimize=lexer_optimize,
                         lexer_table=lexer_table, yacc_optimize=yacc_optimize,
                         yacc_table=yacc_table, yacc_debug=yacc_debug,
                         outputdir=outputdir)

    def p_classdef_or_funcdef(self, p):
        """classdef_or_funcdef : classdef
                               | funcdef
        """
        p[0] = p[1]

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

    def _set_arg(self, args, arg, ensure_kw=False):
        if isinstance(arg, ast.keyword):
            args['keywords'].append(arg)
        elif ensure_kw:
            args['kwargs'] = arg
        else:
            args['args'].append(arg)

    def p_arglist(self, p):
        """arglist : argument comma_opt
                   | argument_comma_list argument comma_opt
                   | argument_comma_list_opt TIMES test comma_argument_list_opt
                   | argument_comma_list_opt TIMES test COMMA POW test
                   | argument_comma_list_opt TIMES test comma_argument_list COMMA POW test
                   | argument_comma_list_opt POW test
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        p0 = {'args': [], 'keywords': [], 'starargs': None, 'kwargs': None}
        if lenp == 3:
            self._set_arg(p0, p1)
        elif lenp == 4 and p2 != '**':
            for arg in p1:
                self._set_arg(p0, arg)
            self._set_arg(p0, p2)
        elif lenp == 4 and p2 == '**':
            if p1 is not None:
                for arg in p1:
                    self._set_arg(p0, arg)
            self._set_arg(p0, p[3], ensure_kw=True)
        elif lenp == 5:
            p0['starargs'], p4 = p[3], p[4]
            if p1 is not None:
                for arg in p1:
                    self._set_arg(p0, arg)
            if p4 is not None:
                for arg in p4:
                    self._set_arg(p0, arg, ensure_kw=True)
        elif lenp == 7:
            p0['starargs'] = p[3]
            if p1 is not None:
                for arg in p1:
                    self._set_arg(p0, arg)
            self._set_arg(p0, p[6], ensure_kw=True)
        elif lenp == 8:
            kwkey = 'kwargs'
            p0['starargs'], p4 = p[3], p[4]
            if p1 is not None:
                for arg in p1:
                    self._set_arg(p0, arg)
            for arg in p4:
                self._set_arg(p0, arg, ensure_kw=True)
            self._set_arg(p0, p[7], ensure_kw=True)
        else:
            assert False
        p[0] = p0

    def p_argument_comma(self, p):
        """argument_comma : argument COMMA"""
        p[0] = [p[1]]

    def p_argument(self, p):
        """argument : test
                    | test comp_for
                    | test EQUALS test
        """
        # Really [keyword '='] test
        # The reason that keywords are test nodes instead of NAME is that using
        # NAME results in an ambiguity.
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
                                      lineno=p1.lineno,
                                      col_offset=p1.col_offset)
        elif lenp == 4:
            p0 = ast.keyword(arg=p1.id, value=p[3])
        else:
            assert False
        p[0] = p0
