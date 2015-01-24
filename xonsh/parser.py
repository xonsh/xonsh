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
        ('left', 'TIMES', 'DIVIDE', 'MOD'), 
        ('left', 'POW'),
        )

    #
    # Grammar as defined by BNF
    #

    def p_single_input(self, p):
        """single_input : NEWLINE 
                        | simple_stmt 
                        | compound_stmt NEWLINE
        """
        p[0] = p[1]

    def p_file_input(self, p):
        """file_input : (NEWLINE | stmt)* ENDMARKER"""
        p[0] = p[1]

    def p_eval_input(self, p):
        """eval_input : testlist NEWLINE* ENDMARKER"""
        p[0] = p[1]

    def p_decorator(self, p):
        """decorator : AT dotted_name [ LPAREN [arglist] RPAREN ] NEWLINE"""
        p[0] = p[1:]

    def p_decorators(self, p):
        """decorators : decorator+"""
        p[0] = p[1:]

    def p_decorated(self, p):
        """decorated : decorators (classdef | funcdef)"""
        p[0] = p[1:]

    def p_funcdef(self, p):
        """funcdef : DEF NAME parameters [RARROW test] COLON suite"""
        p[0] = p[1:]

    def p_parameters(self, p):
        """parameters : LPAREN [typedargslist] RPAREN"""
        p[0] = p[1:]

    def p_typedargslist(self, p):
        """typedargslist : (tfpdef [EQUALS test] (COMMA tfpdef [EQUALS test])* 
                            [COMMA [TIMES [tfpdef] (COMMA tfpdef [EQUALS test])* 
                            [EQUALS POW tfpdef] | POW tfpdef]]
                         | TIMES [tfpdef] (COMMA tfpdef [EQUALS test])* 
                            [COMMA POW tfpdef] | POW tfpdef)
        """
        p[0] = p[1:]

    def p_tfpdef(self, p):
        """tfpdef : NAME [COLON test]"""
        p[0] = p[1:]

    def p_varargslist(self, p):
        """varargslist : (vfpdef [EQUALS test] (COMMA vfpdef [EQUALS test])* 
                          [COMMA [TIMES [vfpdef] (COMMA vfpdef [EQUALS test])* 
                          [COMMA POW vfpdef] | POW vfpdef]]
                       | TIMES [vfpdef] (COMMA vfpdef [EQUALS test])* 
                          [COMMA POW vfpdef] | POW vfpdef)
        """
        p[0] = p[1:]

    def p_vfpdef(self, p):
        """vfpdef : NAME"""
        p[0] = p[1:]

    def p_stmt(self, p):
        """stmt : simple_stmt | compound_stmt"""
        p[0] = p[1:]

    def p_simple_stmt(self, p):
        """simple_stmt : small_stmt (SEMI small_stmt)* [SEMI] NEWLINE"""
        p[0] = p[1:]

    def p_small_stmt(self, p):
        """small_stmt : (expr_stmt | del_stmt | pass_stmt | flow_stmt 
                      | import_stmt | global_stmt | nonlocal_stmt 
                      | assert_stmt)
        """
        p[0] = p[1:]

    def p_expr_stmt(self, p):
        """expr_stmt : testlist_star_expr (augassign (yield_expr|testlist) 
                     | (EQUALS (yield_expr|testlist_star_expr))*)
        """
        p[0] = p[1:]

    def p_testlist_star_expr(self, p):
        """testlist_star_expr : (test|star_expr) (COMMA (test|star_expr))* 
                                [COMMA]
        """
        p[0] = p[1:]

    def p_augassign(self, p):
        """augassign : (PLUSEQUAL | MINUSEQUAL | TIMESEQUAL | DIVEQUAL 
                     | MODEQUAL | AMPERSANDEQUAL | PIPEEQUAL | XOREQUAL
                     | LSHIFTEQUAL | RSHIFTEQUAL | POWEQUAL 
                     | DOUBLEDIVEQUAL)
        """
        p[0] = p[1]

    #
    # For normal assignments, additional restrictions enforced 
    # by the interpreter
    #
    def p_del_stmt(self, p):
        """del_stmt : DEL exprlist"""
        p[0] = p[1:]

    def p_pass_stmt(self, p):
        """pass_stmt : PASS"""
        p[0] = p[1:]

    def p_flow_stmt(self, p):
        """flow_stmt : break_stmt | continue_stmt | return_stmt | raise_stmt 
                     | yield_stmt
        """
        p[0] = p[1]

    def p_break_stmt(self, p):
        """break_stmt : BREAK"""
        p[0] = p[1:]

    def p_continue_stmt(self, p):
        """continue_stmt : CONTINUE"""
        p[0] = p[1:]

    def p_return_stmt(self, p):
        """return_stmt : RETURN [testlist]"""
        p[0] = p[1:]

    def p_yield_stmt(self, p):
        """yield_stmt : yield_expr"""
        p[0] = p[1:]

    def p_raise_stmt(self, p):
        """raise_stmt : RAISE [test [FROM test]]"""
        p[0] = p[1:]

    def p_import_stmt(self, p):
        """import_stmt : import_name | import_from"""
        p[0] = p[1]

    def p_import_name(self, p):
        """import_name : IMPORT dotted_as_names
        """
        p[0] = p[1:]

    def p_import_from(self, p):
        """import_from : (FROM ((PERIOD | ELLIPSIS)* dotted_name 
                                | (PERIOD | ELLIPSIS)+)
                        IMPORT (TIMES | LPAREN import_as_names RPAREN 
                               | import_as_names))
        """
        # note below: the ('.' | '...') is necessary because '...' is 
        # tokenized as ELLIPSIS
        p[0] = p[1:]

    def p_import_as_name(self, p):
        """import_as_name : NAME [AS NAME]
        """
        p[0] = p[1:]

    def p_dotted_as_name(self, p):
        """dotted_as_name : dotted_name [AS NAME]"""
        p[0] = p[1:]

    def p_import_as_names(self, p):
        """import_as_names : import_as_name (COMMA import_as_name)* [COMMA]
        """
        p[0] = p[1:]

    def p_dotted_as_names(self, p):
        """dotted_as_names : dotted_as_name (COMMA dotted_as_name)*"""
        p[0] = p[1:]

    def p_dotted_name(self, p):
        """dotted_name : NAME (PERIOD NAME)*"""
        p[0] = p[1:]

    def p_global_stmt(self, p):
        """global_stmt : GLOBAL NAME (COMMA NAME)*"""
        p[0] = p[1:]

    def p_nonlocal_stmt(self, p):
        """nonlocal_stmt : NONLOCAL NAME (COMMA NAME)*"""
        p[0] = p[1:]

    def p_assert_stmt(self, p):
        """assert_stmt : ASSERT test [COMMA test]"""
        p[0] = p[1:]

    def p_compound_stmt(self, p):
        """compound_stmt : if_stmt | while_stmt | for_stmt | try_stmt 
                         | with_stmt | funcdef | classdef | decorated
        """
        p[0] = p[1]

    def p_if_stmt(self, p):
        """if_stmt : IF test COLON suite (ELIF test COLON suite)* 
                     [ELSE COLON suite]
        """
        p[0] = p[1:]

    def p_while_stmt(self, p):
        """while_stmt : WHILE test COLON suite [ELSE COLON suite]"""
        p[0] = p[1:]

    def p_for_stmt(self, p):
        """for_stmt : FOR exprlist IN testlist COLON suite [ELSE COLON suite]
        """
        p[0] = p[1:]

    def p_(self, p):
        """try_stmt: ('try' ':' suite
           ((except_clause ':' suite)+
            ['else' ':' suite]
            ['finally' ':' suite] |
           'finally' ':' suite))
        """
        p[0] = p[1:]

    def p_(self, p):
        """with_stmt: 'with' with_item (',' with_item)*  ':' suite
        """
        p[0] = p[1:]

    def p_(self, p):
        """with_item: test ['as' expr]
        """
        p[0] = p[1:]

    def p_(self, p):
        """except_clause: 'except' [test ['as' NAME]]
        """
        p[0] = p[1:]

    def p_(self, p):
        """suite: simple_stmt | NEWLINE INDENT stmt+ DEDENT
        """
        p[0] = p[1:]

    def p_(self, p):
        """test: or_test ['if' or_test 'else' test] | lambdef
        """
        p[0] = p[1:]

    def p_(self, p):
        """test_nocond: or_test | lambdef_nocond
        """
        p[0] = p[1:]

    def p_(self, p):
        """lambdef: 'lambda' [varargslist] ':' test
        """
        p[0] = p[1:]

    def p_(self, p):
        """lambdef_nocond: 'lambda' [varargslist] ':' test_nocond
        """
        p[0] = p[1:]

    def p_(self, p):
        """or_test: and_test ('or' and_test)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """and_test: not_test ('and' not_test)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """not_test: 'not' not_test | comparison
        """
        p[0] = p[1:]

    def p_(self, p):
        """comparison: expr (comp_op expr)*
        """
        p[0] = p[1:]

    # <> isn't actually a valid comparison operator in Python. It's here 
    # for the sake of a __future__ import described in PEP 401
    def p_(self, p):
        """comp_op: '<'|'>'|'=='|'>='|'<='|'<>'|'!='|'in'|'not' 'in'|'is'|'is' 'not'
        """
        p[0] = p[1:]

    def p_(self, p):
        """star_expr: '*' expr
        """
        p[0] = p[1:]

    def p_(self, p):
        """expr: xor_expr ('|' xor_expr)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """xor_expr: and_expr ('^' and_expr)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """and_expr: shift_expr ('&' shift_expr)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """shift_expr: arith_expr (('<<'|'>>') arith_expr)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """arith_expr: term (('+'|'-') term)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """term: factor (('*'|'/'|'%'|'//') factor)*
        """
        p[0] = p[1:]

    def p_(self, p):
        """factor: ('+'|'-'|'~') factor | power
        """
        p[0] = p[1:]

    def p_(self, p):
        """power: atom trailer* ['**' factor]
        """
        p[0] = p[1:]

    def p_(self, p):
        """atom: ('(' [yield_expr|testlist_comp] ')' |
       '[' [testlist_comp] ']' |
       '{' [dictorsetmaker] '}' |
       NAME | NUMBER | STRING+ | '...' | 'None' | 'True' | 'False')
        """
        p[0] = p[1:]

    def p_(self, p):
        """testlist_comp: (test|star_expr) ( comp_for | (',' (test|star_expr))* [','] )
        """
        p[0] = p[1:]

    def p_(self, p):
        """trailer: '(' [arglist] ')' | '[' subscriptlist ']' | '.' NAME
        """
        p[0] = p[1:]

    def p_(self, p):
        """subscriptlist: subscript (',' subscript)* [',']
        """
        p[0] = p[1:]

    def p_(self, p):
        """subscript: test | [test] ':' [test] [sliceop]
        """
        p[0] = p[1:]

    def p_(self, p):
        """sliceop: ':' [test]
        """
        p[0] = p[1:]

    def p_(self, p):
        """exprlist: (expr|star_expr) (',' (expr|star_expr))* [',']
        """
        p[0] = p[1:]

    def p_(self, p):
        """testlist: test (',' test)* [',']
        """
        p[0] = p[1:]

    def p_(self, p):
        """dictorsetmaker: ( (test ':' test (comp_for | (',' test ':' test)* [','])) |
                  (test (comp_for | (',' test)* [','])) )
        """
        p[0] = p[1:]

    def p_(self, p):
        """classdef: 'class' NAME ['(' [arglist] ')'] ':' suite
        """
        p[0] = p[1:]

    def p_(self, p):
        """arglist: (argument ',')* (argument [',']
                         |'*' test (',' argument)* [',' '**' test] 
                         |'**' test)
        """
        p[0] = p[1:]

    # The reason that keywords are test nodes instead of NAME is that using 
    # NAME results in an ambiguity. ast.c makes sure it's a NAME.
    def p_(self, p):
        """argument: test [comp_for] | test '=' test  # Really [keyword '='] test
        """
        p[0] = p[1:]

    def p_(self, p):
        """comp_iter: comp_for | comp_if
        """
        p[0] = p[1:]

    def p_(self, p):
        """comp_for: 'for' exprlist 'in' or_test [comp_iter]
        """
        p[0] = p[1:]

    def p_(self, p):
        """comp_if: 'if' test_nocond [comp_iter]
        """
        p[0] = p[1:]

    def p_(self, p):
        """encoding_decl: NAME
        """
        # not used in grammar, but may appear in "node" passed from 
        # Parser to Compiler
        p[0] = p[1:]

    def p_(self, p):
        """yield_expr: 'yield' [yield_arg]
        """
        p[0] = p[1:]

    def p_(self, p):
        """yield_arg: 'from' test | testlist
        """
        p[0] = p[1:]

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

