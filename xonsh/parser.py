"""Implements the xonsh parser"""
from __future__ import print_function, unicode_literals
import re
from collections import Iterable, Sequence

from ply import yacc

from xonsh import ast
from xonsh.lexer import Lexer


class Location(object):
    """Location in a file."""

    def __init__(self, fname, lineno, column=None):
        """Takes a filename, line number, and optionally a column number."""
        self.fname = fname
        self.lineno = lineno
        self.column = column

    def __str__(self):
        s = '{0}:{1}'.format(self.fname, self.lineno)
        if self.column is not None: 
            s += ':{0}'.format(self.column)
        return s

def has_elts(x):
    """Tests if x is an AST node with elements."""
    return isinstance(x, ast.AST) and hasattr(x, 'elts')

def ensure_has_elts(x, lineno=1, col_offset=1):
    """Ensures that x is an AST node with elements."""
    if not has_elts(x):
        if not isinstance(x, Iterable):
            x = [x]
        x = ast.Tuple(elts=x, ctx=ast.Load(), lineno=lineno, 
                      col_offset=col_offset)
    return x
    

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
            'newlines',
            'arglist',
            'func_call',
            'rarrow_test',
            'typedargslist',
            'equals_test',
            'colon_test',
            'tfpdef',
            'comma_tfpdef_list',
            'comma_pow_tfpdef',
            'vfpdef',
            'comma_vfpdef_list',
            'comma_pow_vfpdef',
            'semi',
            'comma',
            'semi_small_stmt_list',
            'comma_test_or_star_expr_list',
            'equals_yield_expr_or_testlist_list',
            'testlist',
            'as_name',
            'period_or_ellipsis',
            'period_or_ellipsis_list',
            'comma_import_as_name_list',
            'comma_dotted_as_name_list',
            'period_name_list',
            'comma_name_list',
            'comma_test',
            'elif_part_list',
            'else_part',
            'finally_part',
            'as_expr',
            'comma_with_item_list',
            'varargslist',
            'or_and_test_list',
            'and_not_test_list',
            'comp_op_expr_list',
            'pipe_xor_expr_list',
            'xor_and_expr_list',
            'ampersand_shift_expr_list',
            'shift_arith_expr_list',
            'pm_term_list',
            'op_factor_list',
            'trailer_list',
            'testlist_comp',
            'yield_expr_or_testlist_comp',
            'dictorsetmaker',
            'comma_subscript_list',
            'test',
            'sliceop',
            'comma_expr_or_star_expr_list',
            'comma_test_list',
            'comp_for',
            'comp_iter',
            'yield_arg',
            'argument_comma_list',
            'comma_argument_list',
            )
        for rule in opt_rules:
            self._opt_rule(rule)

        list_rules = (
            'stmt',
            'comma_tfpdef',
            'comma_vfpdef',
            'semi_small_stmt',
            'comma_test_or_star_expr',
            'equals_yield_expr_or_testlist',
            'period_or_ellipsis',
            'comma_import_as_name',
            'comma_dotted_as_name',
            'period_name',
            'comma_name',
            'elif_part',
            'except_part',
            'comma_with_item',
            'or_and_test',
            'and_not_test',
            'comp_op_expr',
            'pipe_xor_expr',
            'xor_and_expr',
            'ampersand_shift_expr',
            'shift_arith_expr',
            'pm_term',
            'op_factor',
            'trailer',
            'comma_subscript',
            'comma_expr_or_star_expr',
            'comma_test',
            'argument_comma',
            'comma_argument',
            'comma_item',
            )
        for rule in list_rules:
            self._list_rule(rule)

        self.parser = yacc.yacc(module=self, debug=yacc_debug,
            start='start_symbols', 
            optimize=yacc_optimize,
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
        self.lexer.fname = filename
        self.lexer.lineno = 0
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
        setattr(self.__class__, optfunc.__name__, optfunc)

    def _list_rule(self, rulename):
        """For a rule name, creates an associated list rule.
        '_list' is appended to the rule name.
        """
        def listfunc(self, p):
            p[0] = p[1] if len(p) == 2 else p[1] + p[2]
        listfunc.__doc__ = ('{0}_list : {0}\n'
                            '         | {0}_list {0}').format(rulename)
        listfunc.__name__ = 'p_' + rulename + '_list'
        setattr(self.__class__, listfunc.__name__, listfunc)

    def currloc(self, lineno, column=None):
        """Returns the current location."""
        return Location(fname=self.lexer.fname, lineno=lineno,
                        column=column)

    def expr(self, p):
        """Creates an expression for a token."""
        return ast.Expr(value=p, lineno=p.lineno, 
                        col_offset=p.col_offset)

    def token_col(self, t):
        """Gets ths token column"""
        return self.lexer.token_col(t)

    @property
    def lineno(self):
        return self.lexer.lineno

    @property
    def col(self):
        t = self._yacc_lookahead_token()
        if t is not None:
            return self.token_col(t)
        return 1

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

    def p_start_symbols(self, p):
        """start_symbols : single_input
                         | file_input
                         | eval_input
                         | empty
        """
        p[0] = p[1]

    def p_single_input(self, p):
        """single_input : NEWLINE 
                        | simple_stmt 
                        | compound_stmt NEWLINE
        """
        p1 = p[1]
        if p1 == '\n':
            p1 = []
        p0 = ast.Module(body=p1)
        p[0] = p0

    def p_file_input(self, p):
        #"""file_input : newline_or_stmt 
        #              | file_input newline_or_stmt
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

    def p_newlines(self, p):
        """newlines : NEWLINE
                    | newlines NEWLINE
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_eval_input(self, p):
        """eval_input : testlist newlines_opt
                      | testlist newlines_opt ENDMARKER
        """
        p[0] = ast.Module(body=[self.expr(p[1])])

    def p_func_call(self, p):
        """func_call : LPAREN arglist_opt RPAREN"""
        p[0] = p[2]

    def p_decorator(self, p):
        """decorator : AT dotted_name func_call_opt NEWLINE"""
        p[0] = p[1:]

    def p_decorators(self, p):
        """decorators : decorator
                      | decorators decorator
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_classdef_or_funcdef(self, p):
        """classdef_or_funcdef : classdef
                               | funcdef
        """
        p[0] = p[1]

    def p_decorated(self, p):
        """decorated : decorators classdef_or_funcdef"""
        p[0] = p[1] + p[2]

    def p_rarrow_test(self, p):
        """rarrow_test : RARROW test"""
        p[0] = p[1] + p[2]

    def p_funcdef(self, p):
        """funcdef : DEF NAME parameters rarrow_test_opt COLON suite"""
        p[0] = p[1:]

    def p_parameters(self, p):
        """parameters : LPAREN typedargslist_opt RPAREN"""
        p[0] = p[1:]

    def p_equals_test(self, p):
        """equals_test : EQUALS test"""
        p[0] = p[1] + p[2]

    def p_typedargslist(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt 
                         | tfpdef equals_test_opt comma_tfpdef_list_opt COMMA 
                         | tfpdef equals_test_opt comma_tfpdef_list_opt COMMA TIMES tfpdef_opt comma_tfpdef_list_opt 
                         | tfpdef equals_test_opt comma_tfpdef_list_opt COMMA TIMES tfpdef_opt comma_tfpdef_list_opt EQUALS POW tfpdef
                         | tfpdef equals_test_opt comma_tfpdef_list_opt COMMA POW tfpdef
                         | TIMES tfpdef_opt comma_tfpdef_list_opt comma_pow_tfpdef_opt
                         | POW tfpdef
        """
        p[0] = p[1:]

    def p_colon_test(self, p):
        """colon_test : COLON test"""
        p[0] = p[1] + p[2]

    def p_tfpdef(self, p):
        """tfpdef : NAME colon_test_opt"""
        p[0] = p[1] + p[1]

    def p_comma_tfpdef(self, p):
        """comma_tfpdef : COMMA tfpdef equals_test_opt"""
        p[0] = p[1] + p[2] + p[3]

    def p_comma_pow_tfpdef(self, p):
        """comma_pow_tfpdef : COMMA POW tfpdef"""
        p[0] = p[1] + p[2] + p[3]

    def p_varargslist(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt 
                       | vfpdef equals_test_opt comma_vfpdef_list_opt COMMA 
                       | vfpdef equals_test_opt comma_vfpdef_list_opt COMMA TIMES vfpdef_opt comma_vfpdef_list_opt 
                       | vfpdef equals_test_opt comma_vfpdef_list_opt COMMA TIMES vfpdef_opt comma_vfpdef_list_opt COMMA POW vfpdef
                       | vfpdef equals_test_opt comma_vfpdef_list_opt COMMA POW vfpdef
                       | TIMES vfpdef_opt comma_vfpdef_list_opt comma_pow_vfpdef_opt
                       | POW vfpdef
        """
        p[0] = p[1:]

    def p_vfpdef(self, p):
        """vfpdef : NAME"""
        p[0] = p[1:]

    def p_comma_vfpdef(self, p):
        """comma_vfpdef : COMMA vfpdef equals_test_opt"""
        p[0] = p[1] + p[2] + p[3]

    def p_comma_pow_vfpdef(self, p):
        """comma_pow_vfpdef : COMMA POW vfpdef"""
        p[0] = p[1] + p[2] + p[3]

    def p_stmt(self, p):
        """stmt : simple_stmt 
                | compound_stmt
        """
        p[0] = p[1]

    def p_semi(self, p):
        """semi : SEMI"""
        p[0] = p[1]

    def p_semi_small_stmt(self, p):
        """semi_small_stmt : SEMI small_stmt"""
        p[0] = [p[2]]

    def p_simple_stmt(self, p):
        """simple_stmt : small_stmt semi_small_stmt_list_opt semi_opt NEWLINE
                       | small_stmt semi_small_stmt_list semi_opt NEWLINE
                       | small_stmt semi_opt NEWLINE
        """
        p1, p2 = p[1], p[2]
        p0 = [p1]
        if p2 is not None and p2 != ';':
            p0 += p2
        p[0] = p0

    def p_small_stmt(self, p):
        """small_stmt : expr_stmt 
                      | del_stmt 
                      | pass_stmt 
                      | flow_stmt 
                      | import_stmt 
                      | global_stmt 
                      | nonlocal_stmt 
                      | assert_stmt
        """
        p[0] = p[1]

    _augassign_op = {'+=': ast.Add, '-=': ast.Sub, '*=': ast.Mult, 
                     '/=': ast.Div, '%=': ast.Mod, '//=': ast.FloorDiv, 
                     '**=': ast.Pow, '^=': ast.BitXor, '&=': ast.BitAnd, 
                     '|=': ast.BitOr, '<<=': ast.LShift, '>>=': ast.RShift}

    def p_expr_stmt(self, p):
        """expr_stmt : testlist_star_expr augassign yield_expr_or_testlist 
                     | testlist_star_expr equals_yield_expr_or_testlist_list_opt
        """
        p1, p2 = p[1], p[2]
        for targ in p1:
            targ.ctx = ast.Store()
        if len(p) == 3:
            p0 = ast.Assign(targets=p1, value=p2, lineno=self.lineno, 
                            col_offset=self.col)
        elif len(p) == 4:
            op = self._augassign_op[p2]()
            p0 = ast.AugAssign(target=p1[0], op=op, value=p[3], 
                               lineno=self.lineno, col_offset=self.col)
        else:
            assert False
        p[0] = p0

    def p_comma(self, p):
        """comma : COMMA"""
        p[0] = p[1]

    def p_test_or_star_expr(self, p):
        """test_or_star_expr : test
                             | star_expr
        """
        p[0] = p[1]

    def p_comma_test_or_star_expr(self, p):
        """comma_test_or_star_expr : COMMA test_or_star_expr"""
        p[0] = [p[2]]

    def p_testlist_star_expr(self, p):
        """testlist_star_expr : test_or_star_expr comma_test_or_star_expr_list_opt comma_opt
        """
        p1, p2, p3 = p[1], p[2], p[3]
        if p2 is None and p3 is None:
            p0 = [p1]
        else:
            assert False
        p[0] = p0

    def p_augassign(self, p):
        """augassign : PLUSEQUAL 
                     | MINUSEQUAL 
                     | TIMESEQUAL 
                     | DIVEQUAL 
                     | MODEQUAL 
                     | AMPERSANDEQUAL 
                     | PIPEEQUAL 
                     | XOREQUAL
                     | LSHIFTEQUAL 
                     | RSHIFTEQUAL
                     | POWEQUAL 
                     | DOUBLEDIVEQUAL
        """
        p[0] = p[1]

    def p_yield_expr_or_testlist(self, p):
        """yield_expr_or_testlist : yield_expr
                                  | testlist
        """
        p[0] = p[1]

    def p_equals_yield_expr_or_testlist(self, p):
        """equals_yield_expr_or_testlist : EQUALS yield_expr_or_testlist"""
        p[0] = p[2]

    #
    # For normal assignments, additional restrictions enforced 
    # by the interpreter
    #
    def p_del_stmt(self, p):
        """del_stmt : DEL exprlist"""
        p2 = p[2]
        for targ in p2:
            targ.ctx = ast.Del()
        p0 = ast.Delete(targets=p2, lineno=self.lineno, col_offset=self.col)
        p[0] = p0

    def p_pass_stmt(self, p):
        """pass_stmt : PASS"""
        p[0] = ast.Pass(lineno=self.lineno, col_offset=self.col)

    def p_flow_stmt(self, p):
        """flow_stmt : break_stmt 
                     | continue_stmt 
                     | return_stmt 
                     | raise_stmt 
                     | yield_stmt
        """
        p[0] = p[1]

    def p_break_stmt(self, p):
        """break_stmt : BREAK"""
        p[0] = ast.Break(lineno=self.lineno, col_offset=self.col)

    def p_continue_stmt(self, p):
        """continue_stmt : CONTINUE"""
        p[0] = ast.Continue(lineno=self.lineno, col_offset=self.col)

    def p_return_stmt(self, p):
        """return_stmt : RETURN testlist_opt"""
        p[0] = ast.Return(value=p[2], lineno=self.lineno, col_offset=self.col)

    def p_yield_stmt(self, p):
        """yield_stmt : yield_expr"""
        p[0] = self.expr(p[1])

    def p_raise_stmt(self, p):
        """raise_stmt : RAISE 
                      | RAISE test 
                      | RAISE test FROM test
        """
        lenp = len(p)
        cause = None
        if lenp == 2:
            exc = None
        elif lenp == 3:
            exc = p[2]
        elif lenp == 5:
            exc = p[2]
            cause = p[4]
        else:
            assert False
        p0 = ast.Raise(exc=exc, cause=cause, lineno=self.lineno, 
                       col_offset=self.col)
        p[0] = p0

    def p_import_stmt(self, p):
        """import_stmt : import_name 
                       | import_from
        """
        p[0] = p[1]

    def p_import_name(self, p):
        """import_name : IMPORT dotted_as_names
        """
        p[0] = ast.Import(names=p[2], lineno=self.lineno, col_offset=self.col)

    def p_import_from_pre(self, p):
        """import_from_pre : FROM period_or_ellipsis_list_opt dotted_name 
                           | FROM period_or_ellipsis_list
        """
        if len(p) == 3:
            p0 = p[2]
        elif len(p) == 4:
            p2, p3 = p[2], p[3]
            p0 = p3 if p2 is None else p2 + p3
        else:
            assert False
        p[0] = p0

    def p_import_from_post(self, p):
        """import_from_post : TIMES 
                            | LPAREN import_as_names RPAREN 
                            | import_as_names
        """
        if len(p) == 2:
            p0 = p[1]
        elif len(p) == 4:
            p0 = p[2]
        else:
            assert False
        p[0] = p0

    def p_import_from(self, p):
        """import_from : import_from_pre IMPORT import_from_post
        """
        # note below: the ('.' | '...') is necessary because '...' is 
        # tokenized as ELLIPSIS
        p1 = p[1]
        mod = p1.lstrip('.')
        lvl = len(p1) - len(mod)
        mod = mod or None
        p[0] = ast.ImportFrom(module=mod, names=p[3], level=lvl, 
                              lineno=self.lineno, col_offset=self.col)

    def p_period_or_ellipsis(self, p):
        """period_or_ellipsis : PERIOD
                              | ELLIPSIS
        """
        p[0] = p[1]

    def p_as_name(self, p):
        """as_name : AS NAME"""
        p[0] = p[2]

    def p_import_as_name(self, p):
        """import_as_name : NAME as_name_opt"""
        p[0] = ast.alias(name=p[1], asname=p[2])

    def p_comma_import_as_name(self, p):
        """comma_import_as_name : COMMA import_as_name
        """
        p[0] = [p[2]]

    def p_dotted_as_name(self, p):
        """dotted_as_name : dotted_name as_name_opt"""
        p0 = ast.alias(name=p[1], asname=p[2])
        p[0] = p0

    def p_comma_dotted_as_name(self, p):
        """comma_dotted_as_name : COMMA dotted_as_name"""
        p[0] = [p[2]]

    def p_import_as_names(self, p):
        """import_as_names : import_as_name comma_import_as_name_list_opt comma_opt
        """
        p1, p2 = p[1], p[2]
        p0 = [p1]
        if p2 is not None:
            p0.extend(p2)
        p[0] = p0

    def p_dotted_as_names(self, p):
        """dotted_as_names : dotted_as_name comma_dotted_as_name_list_opt"""
        p1, p2 = p[1], p[2]
        p0 = [p1]
        if p2 is not None:
            p0.extend(p2)
        p[0] = p0

    def p_period_name(self, p):
        """period_name : PERIOD NAME"""
        p[0] = p[1] + p[2]

    def p_dotted_name(self, p):
        """dotted_name : NAME period_name_list_opt"""
        p1, p2 = p[1], p[2]
        p0 = p1 if p2 is None else p1 + p2
        p[0] = p0

    def p_comma_name(self, p):
        """comma_name : COMMA NAME"""
        p[0] = p[1] + p[2]

    def p_global_stmt(self, p):
        """global_stmt : GLOBAL NAME comma_name_list_opt"""
        p[0] = p[1:]

    def p_nonlocal_stmt(self, p):
        """nonlocal_stmt : NONLOCAL NAME comma_name_list_opt"""
        p[0] = p[1:]

    def p_comma_test(self, p):
        """comma_test : COMMA test"""
        p[0] = [p[2]]

    def p_assert_stmt(self, p):
        """assert_stmt : ASSERT test comma_test_opt"""
        p2, p3 = p[2], p[3]
        if p3 is not None:
            if len(p3) != 1:
                assert False
            p3 = p3[0]
        p0 = ast.Assert(test=p2, msg=p3, lineno=self.lineno, 
                        col_offset=self.col)
        p[0] = p0

    def p_compound_stmt(self, p):
        """compound_stmt : if_stmt 
                         | while_stmt 
                         | for_stmt 
                         | try_stmt 
                         | with_stmt 
                         | funcdef 
                         | classdef 
                         | decorated
        """
        p[0] = p[1]

    def p_elif_part(self, p):
        """elif_part : ELIF test COLON suite"""
        p[0] = p[1:]

    def p_else_part(self, p):
        """else_part : ELSE COLON suite"""
        p[0] = p[1:]

    def p_if_stmt(self, p):
        """if_stmt : IF test COLON suite elif_part_list_opt else_part_opt
        """
        p[0] = p[1:]

    def p_while_stmt(self, p):
        """while_stmt : WHILE test COLON suite else_part_opt"""
        p[0] = p[1:]

    def p_for_stmt(self, p):
        """for_stmt : FOR exprlist IN testlist COLON suite else_part_opt
        """
        p[0] = p[1:]

    def p_except_part(self, p):
        """except_part : except_clause COLON suite"""
        p[0] = p[1:]

    def p_finally_part(self, p):
        """finally_part : FINALLY COLON suite"""
        p[0] = p[1:]

    def p_try_stmt(self, p):
        """try_stmt : TRY COLON suite except_part_list else_part_opt finally_part_opt
                    | TRY COLON suite finally_part
        """
        p[0] = p[1:]

    def p_with_stmt(self, p):
        """with_stmt : WITH with_item comma_with_item_list_opt COLON suite"""
        p[0] = p[1:]

    def p_as_expr(self, p):
        """as_expr : AS expr"""
        p[0] = p[1:]

    def p_with_item(self, p):
        """with_item : test as_expr_opt"""
        p[0] = p[1:]

    def p_comma_with_item(self, p):
        """comma_with_item : COMMA with_item"""
        p[0] = p[1:]

    def p_except_clause(self, p):
        """except_clause : EXCEPT 
                         | EXCEPT test as_name_opt
        """
        p[0] = p[1:]

    def p_suite(self, p):
        """suite : simple_stmt 
                 | NEWLINE INDENT stmt_list 
        """
        #         | NEWLINE INDENT stmt_list DEDENT
        p[0] = p[1:]

    def p_test(self, p):
        """test : or_test 
                | or_test IF or_test ELSE test
                | lambdef
        """
        if len(p) == 2:
            p0 = p[1]
        else:
            p0 = ast.IfExp(test=p[3], body=p[1], orelse=p[5],
                           lineno=self.lineno, col_offset=self.col)
        p[0] = p0 

    def p_test_nocond(self, p):
        """test_nocond : or_test 
                       | lambdef_nocond
        """
        p[0] = p[1]

    def p_lambdef(self, p):
        """lambdef : LAMBDA varargslist_opt COLON test"""
        p[0] = p[1:]

    def p_lambdef_nocond(self, p):
        """lambdef_nocond : LAMBDA varargslist_opt COLON test_nocond"""
        p[0] = p[1:]

    def p_or_test(self, p):
        """or_test : and_test or_and_test_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        elif len(p2) == 2:
            p0 = ast.BoolOp(op=p2[0], values=[p[1], p2[1]], 
                            lineno=self.lineno, col_offset=self.col)
        else:
            p0 = ast.BoolOp(op=p2[0], values=[p[1]] + p2[1::2], 
                            lineno=self.lineno, col_offset=self.col)
        p[0] = p0

    def p_or_and_test(self, p):
        """or_and_test : OR and_test"""
        p[0] = [ast.Or(), p[2]]

    def p_and_test(self, p):
        """and_test : not_test and_not_test_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        elif len(p2) == 2:
            p0 = ast.BoolOp(op=p2[0], values=[p[1], p2[1]], 
                            lineno=self.lineno, col_offset=self.col)
        else:
            p0 = ast.BoolOp(op=p2[0], values=[p[1]] + p2[1::2], 
                            lineno=self.lineno, col_offset=self.col)
        p[0] = p0

    def p_and_not_test(self, p):
        """and_not_test : AND not_test"""
        p[0] = [ast.And(), p[2]]

    def p_not_test(self, p):
        """not_test : NOT not_test 
                    | comparison
        """
        if len(p) == 2:
            p0 = p[1] 
        else: 
            p0 = ast.UnaryOp(op=ast.Not(), operand=p[2], lineno=self.lineno, 
                             col_offset=self.col)
        p[0] = p0

    def p_comparison(self, p):
        """comparison : expr comp_op_expr_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        else:
            p0 = ast.Compare(left=p[1], ops=p2[::2], comparators=p2[1::2], 
                             lineno=self.lineno, col_offset=self.col)
        p[0] = p0

    def p_comp_op_expr(self, p):
        """comp_op_expr : comp_op expr"""
        p[0] = [p[1], p[2]]

    _comp_ops = {'<': ast.Lt, '>': ast.Gt, '==': ast.Eq, '>=': ast.GtE, 
                 '<=': ast.LtE, '!=': ast.NotEq, 'in': ast.In, 
                 ('not', 'in'): ast.NotIn, 'is': ast.Is, 
                 ('is', 'not'): ast.IsNot}

    def p_comp_op(self, p):
        """comp_op : LT 
                   | GT 
                   | EQ 
                   | GE 
                   | LE 
                   | NE 
                   | IN 
                   | NOT IN 
                   | IS 
                   | IS NOT
        """
        key = p[1] if len(p) == 2 else (p[1], p[2])
        p[0] = self._comp_ops[key]()

    def p_star_expr(self, p):
        """star_expr : TIMES expr"""
        p[0] = p[1:]

    def p_expr(self, p):
        """expr : xor_expr pipe_xor_expr_list_opt"""
        p[0] = p[1] if p[2] is None else p[1] + p[2]

    def p_pipe_xor_expr(self, p):
        """pipe_xor_expr : PIPE xor_expr"""
        p[0] = p[1:]

    def p_xor_expr(self, p):
        """xor_expr : and_expr xor_and_expr_list_opt"""
        p[0] = p[1] if p[2] is None else p[1] + p[2]

    def p_xor_and_expr(self, p):
        """xor_and_expr : XOR and_expr"""
        p[0] = p[1:]

    def p_and_expr(self, p):
        """and_expr : shift_expr ampersand_shift_expr_list_opt"""
        p[0] = p[1] if p[2] is None else p[1] + p[2]

    def p_ampersand_shift_expr(self, p):
        """ampersand_shift_expr : AMPERSAND shift_expr"""
        p[0] = p[1:]

    def p_shift_expr(self, p):
        """shift_expr : arith_expr shift_arith_expr_list_opt"""
        p[0] = p[1] if p[2] is None else p[1] + p[2]

    def p_shift_arith_expr(self, p):
        """shift_arith_expr : LSHIFT arith_expr
                            | RSHIFT arith_expr
        """
        p[0] = p[1:]

    def p_arith_expr(self, p):
        """arith_expr : term pm_term_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        elif len(p2) == 2: 
            p0 = ast.BinOp(left=p[1], op=p2[0], right=p2[1], 
                           lineno=self.lineno, col_offset=self.col)
        else:
            left = p[1]
            for op, right in zip(p2[::2], p2[1::2]):
                left = ast.BinOp(left=left, op=op, right=right, 
                                 lineno=self.lineno, col_offset=self.col)
            p0 = left
        p[0] = p0

    _term_binops = {'+': ast.Add, '-': ast.Sub, '*': ast.Mult, 
                    '/': ast.Div, '%': ast.Mod, '//': ast.FloorDiv}

    def p_pm_term(self, p):
        """pm_term : PLUS term
                   | MINUS term
        """
        op = self._term_binops[p[1]]()
        p[0] = [op, p[2]]

    def p_term(self, p):
        """term : factor op_factor_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1] 
        elif len(p2) == 2:
            p0 = ast.BinOp(left=p[1], op=p2[0], right=p2[1], 
                           lineno=self.lineno, col_offset=self.col)
        else:
            left = p[1]
            for op, right in zip(p2[::2], p2[1::2]):
                left = ast.BinOp(left=left, op=op, right=right, 
                                 lineno=self.lineno, col_offset=self.col)
            p0 = left
        p[0] = p0

    def p_op_factor(self, p):
        """op_factor : TIMES factor
                     | DIVIDE factor
                     | MOD factor
                     | DOUBLEDIV factor
        """
        op = self._term_binops[p[1]]()
        p[0] = [op, p[2]]

    _factor_ops = {'+': ast.UAdd, '-': ast.USub, '~': ast.Invert}

    def p_factor(self, p):
        """factor : PLUS factor
                  | MINUS factor
                  | TILDE factor
                  | power
        """
        if len(p) == 2:
            p0 = p[1]
        else:
            op = self._factor_ops[p[1]]()
            p0 = ast.UnaryOp(op=op, operand=p[2], lineno=self.lineno, 
                             col_offset=self.col)
        p[0] = p0

    def p_power(self, p):
        """power : atom trailer_list_opt 
                 | atom trailer_list_opt POW factor
        """
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = p1
        elif isinstance(p2, (ast.Index, ast.Slice)):
            p0 = ast.Subscript(value=p1, slice=p2, ctx=ast.Load(),
                               lineno=self.lineno, col_offset=self.col)
        else:
            assert False
        # actual power rule
        if len(p) == 5:
            p0 = ast.BinOp(left=p0, op=ast.Pow(), right=p[4], 
                           lineno=self.lineno, col_offset=self.col)
        p[0] = p0

    def p_yield_expr_or_testlist_comp(self, p):
        """yield_expr_or_testlist_comp : yield_expr
                                       | testlist_comp
        """
        p[0] = p[1]

    def p_atom(self, p):
        """atom : LPAREN yield_expr_or_testlist_comp_opt RPAREN 
                | LBRACKET testlist_comp_opt RBRACKET 
                | LBRACE dictorsetmaker_opt RBRACE
                | NAME 
                | number 
                | string_literal_list
                | ELLIPSIS 
                | NONE
                | TRUE 
                | FALSE
        """
        p1 = p[1]
        if len(p) == 2:
            # plain-old atoms
            if isinstance(p1, (ast.Num, ast.Str, ast.Bytes)):
                pass
            elif (p1 is True) or (p1 is False) or (p1 is None):
                p1 = ast.NameConstant(value=p1, lineno=self.lineno, 
                                      col_offset=self.col)
            elif p1 == '...':
                p1 = ast.Ellipsis(lineno=self.lineno, col_offset=self.col)
            else:
                p1 = ast.Name(id=p1, ctx=ast.Load(), lineno=self.lineno, 
                              col_offset=self.col)
            p[0] = p1
            return
        p2 = p[2]
        if p2 is None:
            # empty container atoms
            if p1 == '(':
                p0 = ast.Tuple(elts=[], ctx=ast.Load(), lineno=self.lineno, 
                               col_offset=self.col)
            elif p1 == '[':
                p0 = ast.List(elts=[], ctx=ast.Load(), lineno=self.lineno, 
                              col_offset=self.col)
            elif p1 == '{':
                p0 = ast.Dict(keys=[], values=[], ctx=ast.Load(), 
                              lineno=self.lineno, col_offset=self.col)
            else:
                assert False
        elif p1 == '(':
            # filled, possible group container tuple atoms
            if isinstance(p2, ast.AST):
                p0 = p2
            elif len(p2) == 1 and isinstance(p2[0], ast.AST):
                p0 = p2[0]
            else:
                assert False
        elif p1 == '[':
            if isinstance(p2, ast.GeneratorExp):
                p0 = ast.ListComp(elt=p2.elt, generators=p2.generators, 
                                  lineno=p2.lineno, col_offset=p2.col_offset)
            else:
                p2 = ensure_has_elts(p2)
                p0 = ast.List(elts=p2.elts, ctx=ast.Load(), lineno=self.lineno, 
                              col_offset=self.col)
        elif p1 == '{':
            p0 = p2
        else:
            assert False
        p[0] = p0
       
    def p_string_literal(self, p):
        """string_literal : STRING_LITERAL
                          | RAW_STRING_LITERAL
                          | UNICODE_LITERAL
                          | BYTES_LITERAL
        """
        s = eval(p[1])
        cls = ast.Bytes if p[1].startswith('b') else ast.Str
        p[0] = cls(s=s, lineno=self.lineno, col_offset=self.col)

    def p_string_literal_list(self, p):
        """string_literal_list : string_literal
                               | string_literal_list string_literal
        """
        if len(p) == 3:
            p[1].s += p[2].s
        p[0] = p[1]

    def p_number(self, p):
        """number : INT_LITERAL
                  | HEX_LITERAL
                  | OCT_LITERAL
                  | BIN_LITERAL
                  | FLOAT_LITERAL
        """
        p[0] = ast.Num(n=p[1], lineno=self.lineno, col_offset=self.col)

    def p_testlist_comp(self, p):
        """testlist_comp : test_or_star_expr comp_for 
                         | test_or_star_expr comma_opt
                         | test_or_star_expr comma_test_or_star_expr_list comma_opt
                         | test_or_star_expr comma_test_or_star_expr_list_opt comma_opt
        """
        p1, p2 = p[1], p[2]
        p0 = ensure_has_elts(p1, lineno=self.lineno, col_offset=self.col)
        if len(p) == 3:
            if p2 is None:
                # split out grouping parentheses.
                p0 = p0.elts[0]
            elif p2 == ',':
                pass
            elif 'comps' in p2:
                p0 = ast.GeneratorExp(elt=p0.elts[0], generators=p2['comps'], 
                                      lineno=self.lineno, col_offset=self.col)
            else:
                assert False
        elif len(p) == 4:
            if p2 is not None:
                p0.elts.extend(p2) 
            else:
                assert False
        else:
            assert False
        p[0] = p0

    def p_trailer(self, p):
        """trailer : LPAREN arglist_opt RPAREN 
                   | LBRACKET subscriptlist RBRACKET 
                   | PERIOD NAME
        """
        p1, p2 = p[1], p[2]
        if p1 == '[':
            p0 = p2
        else:
            assert False
        p[0] = p0

    def p_subscriptlist(self, p):
        """subscriptlist : subscript comma_subscript_list_opt comma_opt"""
        p1, p2, p3 = p[1], p[2], p[3]
        if p2 is None and p3 is None:
            p0 = p1
        else:
            assert False
        p[0] = p0

    def p_comma_subscript(self, p):
        """comma_subscript : COMMA subscript"""
        p[0] = p[1:]

    def p_subscript(self, p):
        """subscript : test 
                     | test_opt COLON test_opt sliceop_opt
        """
        if len(p) == 2:
            p0 = ast.Index(value=p[1])
        else:
            p0 = ast.Slice(lower=p[1], upper=p[3], step=p[4])
        p[0] = p0

    def p_sliceop(self, p):
        """sliceop : COLON test_opt"""
        p[0] = p[2]

    def p_expr_or_star_expr(self, p):
        """expr_or_star_expr : expr
                             | star_expr
        """
        p[0] = p[1]

    def p_comma_expr_or_star_expr(self, p):
        """comma_expr_or_star_expr : COMMA expr_or_star_expr"""
        p[0] = [p[2]]

    def p_exprlist(self, p):
        """exprlist : expr_or_star_expr comma_expr_or_star_expr_list_opt comma_opt
                    | expr_or_star_expr comma_expr_or_star_expr_list comma_opt
                    | expr_or_star_expr comma_opt
        """
        p1, p2 = p[1], p[2]
        p3 = p[3] if len(p) == 4 else None
        if p2 is None and p3 is None:
            p0 = [p1]
        elif p2 == ',' and p3 is None:
            p0 = [p1]
        elif p2 is not None:
            p2.insert(0, p1)
            p0 = p2
        else:
            assert False
        p[0] = p0

    def p_testlist(self, p):
        """testlist : test comma_test_list_opt comma_opt
                    | test comma_test_list COMMA
                    | test COMMA
        """
        p1, p2 = p[1], p[2]
        if len(p) == 3:
            if p2 is None:
                p0 = [p1]
            elif p2 == ',':
                p0 = ast.Tuple(elts=[p1], ctx=ast.Load(), lineno=self.lineno, 
                               col_offset=self.col)
            else:
                assert False
        elif len(p) == 4 and p2 is None:
            if p[3] is None:
                pass
            elif not has_elts(p1):
                p1 = ensure_has_elts(p1, lineno=self.lineno, 
                                     col_offset=self.col)
            else:
                assert False
            p0 = p1
        elif len(p) == 4 and p2 is not None:
            p1 = ensure_has_elts(p1, lineno=self.lineno, col_offset=self.col)
            p1.elts += p2
            p0 = p1
        else:
            assert False
        p[0] = p0

    def p_comma_item(self, p):
        """comma_item : COMMA test COLON test"""
        p[0] = [p[2], p[4]]

    def p_dictorsetmaker(self, p):
        """dictorsetmaker : test COLON test comp_for
                          | test COLON test comma_item_list comma_opt
                          | test COLON testlist
                          | test comp_for
                          | testlist 
        """
        p1 = p[1]
        lenp = len(p)
        if lenp == 2:
            p1 = ensure_has_elts(p1)
            p0 = ast.Set(elts=p1.elts, ctx=ast.Load(), lineno=self.lineno, 
                         col_offset=self.col)
        elif lenp == 3:
            comps = p[2].get('comps', [])
            p0 = ast.SetComp(elt=p1, generators=comps, lineno=self.lineno, 
                             col_offset=self.col)
        elif lenp == 4:
            p3 = ensure_has_elts(p[3])
            p0 = ast.Dict(keys=[p1], values=p3.elts, ctx=ast.Load(),
                          lineno=self.lineno, col_offset=self.col)
        elif lenp == 5:
            comps = p[4].get('comps', [])
            p0 = ast.DictComp(key=p1, value=p[3], generators=comps,
                              lineno=self.lineno, col_offset=self.col)
        elif lenp == 6:
            p3, p4 = p[3], p[4]
            keys = [p1] + p4[::2]
            values = [p3] + p4[1::2]
            p0 = ast.Dict(keys=keys, values=values, ctx=ast.Load(),
                          lineno=self.lineno, col_offset=self.col)
        else:
            assert False
        p[0] = p0

    def p_classdef(self, p):
        """classdef : CLASS NAME func_call_opt COLON suite"""
        p[0] = p[1:]

    def p_arglist(self, p):
        """arglist : argument_comma_list_opt argument comma_opt 
                   | argument_comma_list_opt TIMES test comma_argument_list_opt 
                   | argument_comma_list_opt TIMES test comma_argument_list_opt COMMA POW test
                   | argument_comma_list_opt POW test
        """
        p[0] = p[1:]

    def p_argument_comma(self, p):
        """argument_comma : argument COMMA"""
        p[0] = p[1]

    def p_comma_argument(self, p):
        """comma_argument : COMMA argument """
        p[0] = p[1]

    def p_argument(self, p):
        """argument : test comp_for_opt
                    | test EQUALS test
        """
        # Really [keyword '='] test
        # The reason that keywords are test nodes instead of NAME is that using 
        # NAME results in an ambiguity.
        p[0] = p[1:]

    def p_comp_iter(self, p):
        """comp_iter : comp_for 
                     | comp_if
        """
        p[0] = p[1]

    def p_comp_for(self, p):
        """comp_for : FOR exprlist IN or_test comp_iter_opt"""
        targs, it, p5 = p[2], p[4], p[5]
        if len(targs) != 1:
            assert False
        targ = targs[0]
        targ.ctx = ast.Store()
        comp = ast.comprehension(target=targ, iter=it, ifs=[])
        comps = [comp]
        p0 = {'comps': comps}
        if p5 is not None:
            comps += p5.get('comps', [])
            comp.ifs += p5.get('if', [])
        p[0] = p0

    def p_comp_if(self, p):
        """comp_if : IF test_nocond comp_iter_opt"""
        p2, p3 = p[2], p[3]
        p0 = {'if': [p2]}
        if p3 is not None:
            p0['comps'] = p3.get('comps', [])
        p[0] = p0

    def p_encoding_decl(self, p):
        """encoding_decl : NAME"""
        # not used in grammar, but may appear in "node" passed from 
        # Parser to Compiler
        p[0] = p[1]

    def p_yield_expr(self, p):
        """yield_expr : YIELD yield_arg_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = ast.Yield(value=p2, lineno=self.lineno, col_offset=self.col)
        elif p2['from']:
            p0 = ast.YieldFrom(value=p2['val'], lineno=self.lineno, 
                               col_offset=self.col)
        else:
            p0 = ast.Yield(value=p2['val'], lineno=self.lineno, 
                           col_offset=self.col)
        p[0] = p0

    def p_yield_arg(self, p):
        """yield_arg : FROM test 
                     | testlist
        """
        if len(p) == 2:
            p0 = {'from': False, 'val': p[1]}
        else:
            p0 = {'from': True, 'val': p[2]}
        p[0] = p0

    def p_empty(self, p):
        'empty : '
        p[0] = None

    def p_error(self, p):
        if p is None:
            self._parse_error('no further code', '')
        else:
            msg = 'code: {0}'.format(p.value),
            self._parse_error(msg, self.currloc(lineno=p.lineno,
                                   column=self.lexer.token_col(p)))

