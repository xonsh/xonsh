"""Implements the xonsh parser"""
from __future__ import print_function, unicode_literals
import re

from ply import yacc

from xonsh import ast
from xonsh.lexer import Lexer


class Location(object):
    """Location in a file."""

    def __init__(self, fname, lineno, column=None):
        """Takes a filename, line number, and optionally a column number."""
        self.fname = fname
        self.lineno = line
        self.column = column

    def __str__(self):
        s = '{0}:{1}'.format(self.fname, self.lineno)
        if self.column is not None: 
            s += ':{0}'.format(self.column)
        return s


class Parser(object):
    """A class that parses the xonsh language."""

    def __init__(self, lexer_optimize=True, lexer_table='xonsh.lexer_table',
                 yacc_optimize=True, yacc_table='xonsh.yacc_table',
                 yacc_debug=False):
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
        """
        self.lexer = lexer = Lexer(errfunc=self._lexer_errfunc)
        lexer.build(optimize=lexer_optimize, lextab=lexer_table)
        self.tokens = lexer.tokens

        opt_rules = [
            #'abstract_declarator',
            #'assignment_expression',
            ##'declaration_list',
            #'declaration_specifiers',
            #'designation',
            #'expression',
            #'identifier_list',
            #'init_declarator_list',
            #'parameter_type_list',
            #'specifier_qualifier_list',
            #'block_item_list',
            #'type_qualifier_list',
            #'struct_declarator_list'
            ]
        for rule in opt_rules:
            self._create_opt_rule(rule)

        self.parser = yacc.yacc(module=self, debug=yacc_debug,
            start='translation_unit_or_empty', optimize=yacc_optimize,
            tabmodule=yacc_table)

        # Stack of scopes for keeping track of symbols. _scope_stack[-1] is
        # the current (topmost) scope. Each scope is a dictionary that
        # specifies whether a name is a type. If _scope_stack[n][name] is
        # True, 'name' is currently a type in the scope. If it's False,
        # 'name' is used in the scope but not as a type (for instance, if we
        # saw: int name;
        # If 'name' is not a key in _scope_stack[n] then 'name' was not defined
        # in this scope at all.
        self._scope_stack = [dict()]

        # Keeps track of the last token given to yacc (the lookahead token)
        self._last_yielded_token = None

    def parse(self, s, filename='<code>', debug_level=0):
        """Returns an abstract syntax tree of xonsh code.

        Parameters
        ----------
        s : str
            The xonsh code.
        filename : str, optional
            Name of the file.
        debug_level : str, optional
            Debugging level passed down to yacc.

        Returns
        -------
        tree : AST
        """
        self.lexer.filename = filename
        self.lexer.lineno = 0
        self._scope_stack = [dict()]
        self._last_yielded_token = None
        tree = self.cparser.parse(input=s, lexer=self.lexer,
                                  debug=debug_level)
        return tree

    def _lexer_errfunc(self, msg, line, column):
        self._parse_error(msg, self.currloc(line, column))

    def _yacc_lookahead_token(self):
        """Gets the last token seen by the lexer."""
        return self.lexer.last

    #def _create_opt_rule(self, rulename):
    #    """Given a rule name, creates an optional ply.yacc rule
    #        for it. The name of the optional rule is
    #        <rulename>_opt
    #    """
    #    optname = rulename + '_opt'
    #
    #    def optrule(self, p):
    #        p[0] = p[1]
    #
    #    optrule.__doc__ = '%s : empty\n| %s' % (optname, rulename)
    #    optrule.__name__ = 'p_%s' % optname
    #    setattr(self.__class__, optrule.__name__, optrule)

    def currloc(self, lineno, column=None):
        """Returns the current location."""
        return Location(fname=self.lexer.fname, lineno=lineno,
                        column=column)

    def _parse_error(self, msg, loc):
        raise SyntaxError('{0}: {1}'.format(loc, msg))

    #
    # Precedence of operators
    #
    precedence = (
        ('left', 'LOGIC_OR'),
        ('left', 'LOGIC_AND'),
        ('left', 'PIPE'),
        ('left', 'XOR'),
        ('left', 'AMPERSAND'),
        ('left', 'EQ', 'NE'),
        ('left', 'GT', 'GE', 'LT', 'LE'),
        ('left', 'RSHIFT', 'LSHIFT'),
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'MOD', 'POW')
        )

    #
    # Grammar as defined by BNF
    #

    def p_empty(self, p):
        'empty : '
        p[0] = None

    def p_error(self, p):
        if p:
            msg = 'code: {0}'.format(p.value),
            self._parse_error(msg, self.currloc(lineno=p.lineno,
                                   column=self.lexer.token_col(p)))
        else:
            self._parse_error('no further code', '')

