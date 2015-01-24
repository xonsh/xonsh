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

        opt_rules = (
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
            )
        for rule in opt_rules:
            self._opt_rule(rule)

        self.parser = yacc.yacc(module=self, debug=yacc_debug,
            start='translation_unit_or_empty', optimize=yacc_optimize,
            tabmodule=yacc_table)

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
        tree = self.parser.parse(input=s, lexer=self.lexer,
                                  debug=debug_level)
        return tree

    def _lexer_errfunc(self, msg, line, column):
        self._parse_error(msg, self.currloc(line, column))

    def _yacc_lookahead_token(self):
        """Gets the last token seen by the lexer."""
        return self.lexer.last

    def _opt_rule(self, rulename):
        """For a rule name, creates an associated optional rule.
        '_opt' is appended to the rule name.
        """
        def optfunc(self, p):
            p[0] = p[1]
        optfunc.__doc__ = ('{0}_opt : empty\n'
                           '        | {0}').format(rulename)
        optfunc.__name__ = 'p_' + rulename + '_opt'
        setattr(self.__class__, optrule.__name__, optfunc)

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
        ('left', 'TIMES', 'DIVIDE', 'DOUBLEDIV', 'MOD'), 
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
        """file_input : newline_or_stmt ENDMARKER
                      | file_input newline_or_stmt ENDMARKER
        """
        if len(p) == 3:
            # newline_or_stmt ENDMARKER
            p[0] = p[1]
        else:
            # file_input newline_or_stmt ENDMARKER
            p[0] = p[1] + p[2]

    def p_newline_or_stmt(self, p):
        """newline_or_stmt : NEWLINE 
                           | stmt
        """
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
        """typedargslist : (tfpdef [EQUALS test] (COMMA tfpdef [EQUALS test])* [COMMA [TIMES [tfpdef] (COMMA tfpdef [EQUALS test])* [EQUALS POW tfpdef] | POW tfpdef]] 
                         | TIMES [tfpdef] (COMMA tfpdef [EQUALS test])* [COMMA POW tfpdef] 
                         | POW tfpdef)
        """
        p[0] = p[1:]

    def p_tfpdef(self, p):
        """tfpdef : NAME [COLON test]"""
        p[0] = p[1:]

    def p_varargslist(self, p):
        """varargslist : (vfpdef [EQUALS test] (COMMA vfpdef [EQUALS test])* [COMMA [TIMES [vfpdef] (COMMA vfpdef [EQUALS test])* [COMMA POW vfpdef] | POW vfpdef]]
                       | TIMES [vfpdef] (COMMA vfpdef [EQUALS test])* [COMMA POW vfpdef] 
                       | POW vfpdef)
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
        """testlist_star_expr : (test|star_expr) (COMMA (test|star_expr))* [COMMA]
        """
        p[0] = p[1:]

    def p_augassign(self, p):
        """augassign : PLUSEQUAL | MINUSEQUAL | TIMESEQUAL | DIVEQUAL 
                     | MODEQUAL | AMPERSANDEQUAL | PIPEEQUAL | XOREQUAL
                     | LSHIFTEQUAL | RSHIFTEQUAL | POWEQUAL 
                     | DOUBLEDIVEQUAL
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
        """import_from : (FROM ((PERIOD | ELLIPSIS)* dotted_name | (PERIOD | ELLIPSIS)+) IMPORT (TIMES | LPAREN import_as_names RPAREN | import_as_names))
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
        """if_stmt : IF test COLON suite (ELIF test COLON suite)* [ELSE COLON suite]
        """
        p[0] = p[1:]

    def p_while_stmt(self, p):
        """while_stmt : WHILE test COLON suite [ELSE COLON suite]"""
        p[0] = p[1:]

    def p_for_stmt(self, p):
        """for_stmt : FOR exprlist IN testlist COLON suite [ELSE COLON suite]
        """
        p[0] = p[1:]

    def p_try_stmt(self, p):
        """try_stmt : (TRY COLON suite ((except_clause COLON suite)+ [ELSE COLON suite] [FINALLY COLON suite] | FINALLY COLON suite))
        """
        p[0] = p[1:]

    def p_with_stmt(self, p):
        """with_stmt : WITH with_item (COMMA with_item)* COLON suite"""
        p[0] = p[1:]

    def p_with_item(self, p):
        """with_item : test [AS expr]"""
        p[0] = p[1:]

    def p_except_clause(self, p):
        """except_clause : EXCEPT [test [AS NAME]]"""
        p[0] = p[1:]

    def p_suite(self, p):
        """suite : simple_stmt | NEWLINE INDENT stmt+ DEDENT"""
        p[0] = p[1:]

    def p_test(self, p):
        """test : or_test [IF or_test ELSE test] | lambdef"""
        p[0] = p[1:]

    def p_test_nocond(self, p):
        """test_nocond : or_test | lambdef_nocond"""
        p[0] = p[1:]

    def p_lambdef(self, p):
        """lambdef : LAMBDA [varargslist] COLON test"""
        p[0] = p[1:]

    def p_lambdef_nocond(self, p):
        """lambdef_nocond : LAMBDA [varargslist] COLON test_nocond"""
        p[0] = p[1:]

    def p_or_test(self, p):
        """or_test : and_test (OR and_test)*"""
        p[0] = p[1:]

    def p_and_test(self, p):
        """and_test : not_test (AND not_test)*"""
        p[0] = p[1:]

    def p_not_test(self, p):
        """not_test : NOT not_test | comparison"""
        p[0] = p[1:]

    def p_comparison(self, p):
        """comparison : expr (comp_op expr)*"""
        p[0] = p[1:]

    def p_comp_op(self, p):
        """comp_op : LT | GT | EQ | GE | LE | NE | IN | NOT IN | IS | IS NOT
        """
        p[0] = p[1:]

    def p_star_expr(self, p):
        """star_expr : TIMES expr"""
        p[0] = p[1:]

    def p_expr(self, p):
        """expr : xor_expr (PIPE xor_expr)*"""
        p[0] = p[1:]

    def p_xor_expr(self, p):
        """xor_expr : and_expr (XOR and_expr)*"""
        p[0] = p[1:]

    def p_and_expr(self, p):
        """and_expr : shift_expr (AMPERSAND shift_expr)*"""
        p[0] = p[1:]

    def p_shift_expr(self, p):
        """shift_expr : arith_expr ((LSHIFT|RSHIFT) arith_expr)*"""
        p[0] = p[1:]

    def p_arith_expr(self, p):
        """arith_expr : term ((PLUS|MINUS) term)*"""
        p[0] = p[1:]

    def p_term(self, p):
        """term : factor ((TIMES|DIVIDE|MOD|DOUBLEDIV) factor)*"""
        p[0] = p[1:]

    def p_factor(self, p):
        """factor : (PLUS|MINUS|TILDE) factor | power"""
        p[0] = p[1:]

    def p_power(self, p):
        """power : atom trailer* [POW factor]"""
        p[0] = p[1:]

    def p_atom(self, p):
        """atom : (LPAREN [yield_expr|testlist_comp] RPAREN 
                | LBRACKET [testlist_comp] RBRAKET 
                | LBRACE [dictorsetmaker] RBRACE
                | NAME | NUMBER | STRING_LITERAL+ | ELLIPSIS | 'None' 
                | 'True' | 'False')
        """
        p[0] = p[1:]

    def p_testlist_comp(self, p):
        """testlist_comp : (test|star_expr) (comp_for | (COMMA (test|star_expr))* [COMMA] )
        """
        p[0] = p[1:]

    def p_trailer(self, p):
        """trailer : LPAREN [arglist] RPAREN 
                   | LBRACKET subscriptlist RBRAKET 
                   | PERIOD NAME
        """
        p[0] = p[1:]

    def p_subscriptlist(self, p):
        """subscriptlist : subscript (COMMA subscript)* [COMMA]"""
        p[0] = p[1:]

    def p_subscript(self, p):
        """subscript : test | [test] COLON [test] [sliceop]"""
        p[0] = p[1:]

    def p_sliceop(self, p):
        """sliceop : COLON [test]"""
        p[0] = p[1:]

    def p_exprlist(self, p):
        """exprlist : (expr|star_expr) (COMMA (expr|star_expr))* [COMMA]"""
        p[0] = p[1:]

    def p_testlist(self, p):
        """testlist : test (COMMA test)* [COMMA]"""
        p[0] = p[1:]

    def p_dictorsetmaker(self, p):
        """dictorsetmaker : ( (test COLON test (comp_for 
                          | (COMMA test COLON test)* [COMMA])) 
                          | (test (comp_for | (COMMA test)* [COMMA])) )
        """
        p[0] = p[1:]

    def p_classdef(self, p):
        """classdef : CLASS NAME [RPAREN [arglist] LPAREN] COLON suite"""
        p[0] = p[1:]

    def p_arglist(self, p):
        """arglist : (argument COMMA)* (argument [COMMA]
                   | TIMES test (COMMA argument)* [COMMA POW test] 
                   | POW test)
        """
        p[0] = p[1:]

    def p_argument(self, p):
        """argument : test [comp_for] | test EQUALS test  """
        # Really [keyword '='] test
        # The reason that keywords are test nodes instead of NAME is that using 
        # NAME results in an ambiguity.
        p[0] = p[1:]

    def p_comp_iter(self, p):
        """comp_iter : comp_for | comp_if"""
        p[0] = p[1:]

    def p_comp_for(self, p):
        """comp_for : FOR exprlist IN or_test [comp_iter]"""
        p[0] = p[1:]

    def p_comp_if(self, p):
        """comp_if : IF test_nocond [comp_iter]"""
        p[0] = p[1:]

    def p_encoding_decl(self, p):
        """encoding_decl : NAME"""
        # not used in grammar, but may appear in "node" passed from 
        # Parser to Compiler
        p[0] = p[1:]

    def p_yield_expr(self, p):
        """yield_expr : YIELD [yield_arg]"""
        p[0] = p[1:]

    def p_yield_arg(self, p):
        """yield_arg : FROM test | testlist"""
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

