"""Implements the xonsh parser"""
import os
import sys
from collections import Iterable, Sequence, Mapping

from ply import yacc

from xonsh import ast
from xonsh.lexer import Lexer
from xonsh.tools import VER_3_4, VER_3_5, VER_MAJOR_MINOR, V_MAJOR_MINOR, \
    docstring_by_version


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
        x = ast.Tuple(elts=x,
                      ctx=ast.Load(),
                      lineno=lineno,
                      col_offset=col_offset)
    return x


def empty_list(lineno=None, col=None):
    """Creates the AST node for an empty list."""
    return ast.List(elts=[], ctx=ast.Load(), lineno=lineno, col_offset=col)


def binop(x, op, y, lineno=None, col=None):
    """Creates the AST node for a binary operation."""
    return ast.BinOp(left=x, op=op, right=y, lineno=lineno, col_offset=col)


def call_split_lines(x, lineno=None, col=None):
    """Creates the AST node for calling the 'splitlines' attribute of an
    object, nominally a string.
    """
    return ast.Call(func=ast.Attribute(value=x,
                                       attr='splitlines',
                                       ctx=ast.Load(),
                                       lineno=lineno,
                                       col_offset=col),
                    args=[],
                    keywords=[],
                    starargs=None,
                    kwargs=None,
                    lineno=lineno,
                    col_offset=col)


def ensure_list_from_str_or_list(x, lineno=None, col=None):
    """Creates the AST node for the following expression::

        [x] if isinstance(x, str) else x

    Somewhat useful.
    """
    return ast.IfExp(test=ast.Call(func=ast.Name(id='isinstance',
                                                 ctx=ast.Load(),
                                                 lineno=lineno,
                                                 col_offset=col),
                                   args=[x, ast.Name(id='str',
                                                     ctx=ast.Load(),
                                                     lineno=lineno,
                                                     col_offset=col)],
                                   keywords=[],
                                   starargs=None,
                                   kwargs=None,
                                   lineno=lineno,
                                   col_offset=col),
                     body=ast.List(elts=[x],
                                   ctx=ast.Load(),
                                   lineno=lineno,
                                   col_offset=col),
                     orelse=x,
                     lineno=lineno,
                     col_offset=col)


def xonsh_call(name, args, lineno=None, col=None):
    """Creates the AST node for calling a function of a given name."""
    return ast.Call(func=ast.Name(id=name,
                                  ctx=ast.Load(),
                                  lineno=lineno,
                                  col_offset=col),
                    args=args,
                    keywords=[],
                    starargs=None,
                    kwargs=None,
                    lineno=lineno,
                    col_offset=col)


def xonsh_help(x, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh_help__() function."""
    return xonsh_call('__xonsh_help__', [x], lineno=lineno, col=col)


def xonsh_superhelp(x, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh_superhelp__() function."""
    return xonsh_call('__xonsh_superhelp__', [x], lineno=lineno, col=col)


def xonsh_regexpath(x, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh_regexpath__() function."""
    return xonsh_call('__xonsh_regexpath__', [x], lineno=lineno, col=col)


def load_ctx(x):
    """Recursively sets ctx to ast.Load()"""
    if not hasattr(x, 'ctx'):
        return
    x.ctx = ast.Load()
    if isinstance(x, (ast.Tuple, ast.List)):
        for e in x.elts:
            load_ctx(e)
    elif isinstance(x, ast.Starred):
        load_ctx(x.value)


def store_ctx(x):
    """Recursively sets ctx to ast.Store()"""
    if not hasattr(x, 'ctx'):
        return
    x.ctx = ast.Store()
    if isinstance(x, (ast.Tuple, ast.List)):
        for e in x.elts:
            store_ctx(e)
    elif isinstance(x, ast.Starred):
        store_ctx(x.value)


def empty_list_if_newline(x):
    return [] if x == '\n' else x


class Parser(object):
    """A class that parses the xonsh language."""

    def __init__(self,
                 lexer_optimize=True,
                 lexer_table='xonsh.lexer_table',
                 yacc_optimize=True,
                 yacc_table='xonsh.parser_table',
                 yacc_debug=False,
                 outputdir=None):
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
        self.lexer = lexer = Lexer()
        self.tokens = lexer.tokens

        opt_rules = [
            'newlines', 'arglist', 'func_call', 'rarrow_test', 'typedargslist',
            'equals_test', 'colon_test', 'tfpdef', 'comma_tfpdef_list',
            'comma_pow_tfpdef', 'vfpdef', 'comma_vfpdef_list',
            'comma_pow_vfpdef', 'equals_yield_expr_or_testlist_list',
            'testlist', 'as_name', 'period_or_ellipsis_list',
            'comma_import_as_name_list', 'comma_dotted_as_name_list',
            'comma_name_list', 'comma_test', 'elif_part_list', 'finally_part',
            'varargslist', 'or_and_test_list', 'and_not_test_list',
            'comp_op_expr_list', 'xor_and_expr_list',
            'ampersand_shift_expr_list', 'shift_arith_expr_list',
            'op_factor_list', 'trailer_list', 'testlist_comp',
            'yield_expr_or_testlist_comp', 'dictorsetmaker',
            'comma_subscript_list', 'test', 'sliceop', 'comp_iter',
            'yield_arg', 'test_comma_list',]
        if VER_MAJOR_MINOR <= VER_3_4:
            opt_rules += ['argument_comma_list', 'comma_argument_list',]
        for rule in opt_rules:
            self._opt_rule(rule)

        list_rules = [
            'comma_tfpdef', 'comma_vfpdef', 'semi_small_stmt',
            'comma_test_or_star_expr', 'period_or_ellipsis',
            'comma_import_as_name', 'comma_dotted_as_name', 'period_name',
            'comma_name', 'elif_part', 'except_part', 'comma_with_item',
            'or_and_test', 'and_not_test', 'comp_op_expr', 'pipe_xor_expr',
            'xor_and_expr', 'ampersand_shift_expr', 'shift_arith_expr',
            'pm_term', 'op_factor', 'trailer', 'comma_subscript',
            'comma_expr_or_star_expr', 'comma_test', 'comma_argument', 'comma_item', 
            'attr_period_name', 'test_comma', 'equals_yield_expr_or_testlist', 
            'test_or_star_expr']
        if VER_MAJOR_MINOR <= VER_3_4:
            list_rules += ['argument_comma',]
        for rule in list_rules:
            self._list_rule(rule)

        yacc_kwargs = dict(module=self,
                           debug=yacc_debug,
                           start='start_symbols',
                           optimize=yacc_optimize,
                           tabmodule=yacc_table)
        if not yacc_debug:
            yacc_kwargs['errorlog'] = yacc.NullLogger()
        if outputdir is not None:
            yacc_kwargs['outputdir'] = outputdir
        self.parser = yacc.yacc(**yacc_kwargs)

        # Keeps track of the last token given to yacc (the lookahead token)
        self._last_yielded_token = None

    def reset(self):
        """Resets for clean parsing."""
        self.lexer.reset()
        self._last_yielded_token = None

    def parse(self, s, filename='<code>', mode='exec', debug_level=0):
        """Returns an abstract syntax tree of xonsh code.

        Parameters
        ----------
        s : str
            The xonsh code.
        filename : str, optional
            Name of the file.
        mode : str, optional
            Execution mode, one of: exec, eval, or single.
        debug_level : str, optional
            Debugging level passed down to yacc.

        Returns
        -------
        tree : AST
        """
        self.reset()
        self.lexer.fname = filename
        tree = self.parser.parse(input=s, lexer=self.lexer, debug=debug_level)
        # hack for getting modes right
        if mode == 'single':
            if isinstance(tree, ast.Expression):
                tree = ast.Interactive(body=[self.expr(tree.body)])
            elif isinstance(tree, ast.Module):
                tree = ast.Interactive(body=tree.body)
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
        return Location(fname=self.lexer.fname, lineno=lineno, column=column)

    def expr(self, p):
        """Creates an expression for a token."""
        return ast.Expr(value=p, lineno=p.lineno, col_offset=p.col_offset)

    def token_col(self, t):
        """Gets ths token column"""
        return t.lexpos

    @property
    def lineno(self):
        if self.lexer.last is None:
            return 0
        else:
            return self.lexer.last.lineno

    @property
    def col(self):
        t = self._yacc_lookahead_token()
        if t is not None:
            return self.token_col(t)
        return 1

    def _parse_error(self, msg, loc):
        err = SyntaxError('{0}: {1}'.format(loc, msg))
        err.loc = loc
        raise err

    #
    # Precedence of operators
    #
    precedence = (('left', 'PIPE'), ('left', 'XOR'), ('left', 'AMPERSAND'),
                  ('left', 'EQ', 'NE'), ('left', 'GT', 'GE', 'LT', 'LE'),
                  ('left', 'RSHIFT', 'LSHIFT'), ('left', 'PLUS', 'MINUS'),
                  ('left', 'TIMES', 'DIVIDE', 'DOUBLEDIV', 'MOD'),
                  ('left', 'POW'), )

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
        """single_input : compound_stmt NEWLINE
        """
        p1 = empty_list_if_newline(p[1])
        p0 = ast.Interactive(body=p1)
        p[0] = p0

    def p_file_input(self, p):
        """file_input : file_stmts"""
        p[0] = ast.Module(body=p[1])

    def p_file_stmts(self, p):
        """file_stmts : newline_or_stmt
                      | file_stmts newline_or_stmt
        """
        if len(p) == 2:
            # newline_or_stmt ENDMARKER
            p1 = empty_list_if_newline(p[1])
            p[0] = p1
        else:
            # file_input newline_or_stmt ENDMARKER
            p2 = empty_list_if_newline(p[2])
            p[0] = p[1] + p2

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
        """
        p[0] = ast.Expression(body=p[1])

    def p_func_call(self, p):
        """func_call : LPAREN arglist_opt RPAREN"""
        p[0] = p[2]

    def p_attr_period_name(self, p):
        """attr_period_name : PERIOD NAME"""
        p[0] = [p[2]]

    def p_attr_name(self, p):
        """attr_name : NAME
                     | NAME attr_period_name_list
        """
        p1 = p[1]
        name = ast.Name(id=p1,
                        ctx=ast.Load(),
                        lineno=self.lineno,
                        col_offset=self.col)
        if len(p) == 2:
            p0 = name
        else:
            p2 = p[2]
            p0 = ast.Attribute(value=name,
                               attr=p2[0],
                               ctx=ast.Load(),
                               lineno=self.lineno,
                               col_offset=self.col)
            for a in p2[1:]:
                p0 = ast.Attribute(value=p0,
                                   attr=a,
                                   ctx=ast.Load(),
                                   lineno=self.lineno,
                                   col_offset=self.col)
        p[0] = p0

    def p_decorator(self, p):
        """decorator : AT attr_name NEWLINE
                     | AT attr_name func_call NEWLINE
        """
        lenp = len(p)
        name = p[2]
        p3 = p[3] if lenp > 3 else None
        if lenp == 4:
            p0 = name
        elif p3 is None:
            p0 = ast.Call(func=name,
                          args=[],
                          keywords=[],
                          starargs=None,
                          kwargs=None,
                          lineno=self.lineno,
                          col_offset=self.col)
        else:
            p0 = ast.Call(func=name,
                          lineno=self.lineno,
                          col_offset=self.col, **p3)
        p[0] = p0

    def p_decorators(self, p):
        """decorators : decorator
                      | decorators decorator
        """
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    @docstring_by_version(
        v34=\
        """classdef_or_funcdef : classdef
                               | funcdef
        """,
        v35=\
        """classdef_or_funcdef : classdef
                               | funcdef
                               | async_funcdef
        """,
        )
    def p_classdef_or_funcdef(self, p):
        p[0] = p[1]

    def p_decorated(self, p):
        """decorated : decorators classdef_or_funcdef"""
        p1, p2 = p[1], p[2]
        p2[0].decorator_list = p1
        p[0] = p2

    def p_rarrow_test(self, p):
        """rarrow_test : RARROW test"""
        p[0] = p[2]

    def p_funcdef(self, p):
        """funcdef : DEF NAME parameters rarrow_test_opt COLON suite"""
        f = ast.FunctionDef(name=p[2],
                            args=p[3],
                            returns=p[4],
                            body=p[6],
                            decorator_list=[],
                            lineno=self.lineno,
                            col_offset=self.col)
        p[0] = [f]

    def p_async_funcdef(self, p):
        """async_funcdef : ASYNC funcdef"""
        f = p[2][0]
        p[0] = [ast.AsyncFunctionDef(**f.__dict__)]

    def p_parameters(self, p):
        """parameters : LPAREN typedargslist_opt RPAREN"""
        p2 = p[2]
        if p2 is None:
            p2 = ast.arguments(args=[],
                               vararg=None,
                               kwonlyargs=[],
                               kw_defaults=[],
                               kwarg=None,
                               defaults=[])
        p[0] = p2

    def p_equals_test(self, p):
        """equals_test : EQUALS test"""
        p[0] = p[2]

    def p_typedargslist(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt
                         | tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt COMMA POW vfpdef
                         | tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list_opt
                         | tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list COMMA POW tfpdef
                         | tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt POW tfpdef
                         | TIMES tfpdef_opt comma_tfpdef_list comma_pow_tfpdef_opt
                         | TIMES tfpdef_opt comma_pow_tfpdef_opt
                         | POW tfpdef
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        p3 = p[3] if lenp > 3 else None
        p4 = p[4] if lenp > 4 else None
        # skip p5
        p6 = p[6] if lenp > 6 else None
        p7 = p[7] if lenp > 7 else None
        # skip p8
        p9 = p[9] if lenp > 9 else None
        p10 = p[10] if lenp > 10 else None
        p0 = ast.arguments(args=[],
                           vararg=None,
                           kwonlyargs=[],
                           kw_defaults=[],
                           kwarg=None,
                           defaults=[])
        if lenp == 3:
            p0.kwarg = p2
        elif lenp == 4:
            self._set_var_args(p0, p2, None)
            p0.kwarg = p3
        elif lenp == 5 and p1 != '*':
            # x
            self._set_regular_args(p0, p1, p2, p3, p4)
        elif lenp == 5 and p1 == '*':
            self._set_var_args(p0, p2, p3)  # *args
            if p4 is not None:
                # *args, x, **kwargs
                p0.kwarg = p4
        elif lenp == 7:
            # x, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            p0.kwarg = p[6]
        elif lenp == 8:
            # x, *args
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, p7)
        elif lenp == 10:
            # x, *args, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, None)
            p0.kwarg = p9
        elif lenp == 11:
            # x, *args, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, p7)
            p0.kwarg = p10
        else:
            assert False
        p[0] = p0

    def p_colon_test(self, p):
        """colon_test : COLON test"""
        p[0] = p[2]

    def p_tfpdef(self, p):
        """tfpdef : NAME colon_test_opt"""
        p[0] = ast.arg(arg=p[1], annotation=p[2])

    def p_comma_tfpdef(self, p):
        """comma_tfpdef : COMMA
                        | COMMA tfpdef equals_test_opt
        """
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = [{'arg': p[2], 'default': p[3]}]

    def p_comma_pow_tfpdef(self, p):
        """comma_pow_tfpdef : COMMA POW tfpdef"""
        p[0] = p[3]

    def _set_args_def(self, argmts, vals, kwargs=False):
        args, defs = (argmts.kwonlyargs, argmts.kw_defaults) if kwargs else \
                     (argmts.args, argmts.defaults)
        for v in vals:
            args.append(v['arg'])
            d = v['default']
            if kwargs or (d is not None):
                defs.append(d)

    def _set_regular_args(self, p0, p1, p2, p3, p4):
        if p2 is None and p3 is None:
            # x
            p0.args.append(p1)
        elif p2 is not None and p3 is None:
            # x=42
            p0.args.append(p1)
            p0.defaults.append(p2)
        elif p2 is None and p3 is not None:
            # x, y and x, y=42
            p0.args.append(p1)
            self._set_args_def(p0, p3)
        else:
            # x=42, y=42
            p0.args.append(p1)
            p0.defaults.append(p2)
            self._set_args_def(p0, p3)

    def _set_var_args(self, p0, vararg, kwargs):
        if vararg is None:
            self._set_args_def(p0, kwargs, kwargs=True)
        elif vararg is not None and kwargs is None:
            # *args
            p0.vararg = vararg
        elif vararg is not None and kwargs is not None:
            # *args, x and *args, x, y and *args, x=10 and *args, x=10, y
            # and *args, x, y=10, and *args, x=42, y=65
            p0.vararg = vararg
            self._set_args_def(p0, kwargs, kwargs=True)
        else:
            assert False

    def p_varargslist(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt
                       | vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt COMMA POW vfpdef
                       | vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list_opt
                       | vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list COMMA POW vfpdef
                       | vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt POW vfpdef
                       | TIMES vfpdef_opt comma_vfpdef_list comma_pow_vfpdef_opt
                       | TIMES vfpdef_opt comma_pow_vfpdef_opt
                       | POW vfpdef
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        p3 = p[3] if lenp > 3 else None
        p4 = p[4] if lenp > 4 else None
        # skip p5
        p6 = p[6] if lenp > 6 else None
        p7 = p[7] if lenp > 7 else None
        # skip p8
        p9 = p[9] if lenp > 9 else None
        p10 = p[10] if lenp > 10 else None
        p0 = ast.arguments(args=[],
                           vararg=None,
                           kwonlyargs=[],
                           kw_defaults=[],
                           kwarg=None,
                           defaults=[])
        if lenp == 3:
            p0.kwarg = p2
        elif lenp == 4:
            self._set_var_args(p0, p2, None)
            p0.kwarg = p3
        elif lenp == 5 and p1 != '*':
            # x
            self._set_regular_args(p0, p1, p2, p3, p4)
        elif lenp == 5 and p1 == '*':
            self._set_var_args(p0, p2, p3)  # *args
            if p4 is not None:
                # *args, x, **kwargs
                p0.kwarg = p4
        elif lenp == 7:
            # x, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            p0.kwarg = p6
        elif lenp == 8:
            # x, *args
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, p7)
        elif lenp == 10:
            # x, *args, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, None)
            p0.kwarg = p9
        elif lenp == 11:
            # x, *args, **kwargs
            self._set_regular_args(p0, p1, p2, p3, p4)
            self._set_var_args(p0, p6, p7)
            p0.kwarg = p10
        else:
            assert False
        p[0] = p0

    def p_vfpdef(self, p):
        """vfpdef : NAME"""
        p[0] = ast.arg(arg=p[1], annotation=None)

    def p_comma_vfpdef(self, p):
        """comma_vfpdef : COMMA
                        | COMMA vfpdef equals_test_opt
        """
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = [{'arg': p[2], 'default': p[3]}]

    def p_comma_pow_vfpdef(self, p):
        """comma_pow_vfpdef : COMMA POW vfpdef"""
        p[0] = p[3]

    def p_stmt(self, p):
        """stmt : simple_stmt
                | compound_stmt
        """
        p[0] = p[1]

    def p_stmt_list(self, p):
        """stmt_list : stmt
                     | stmt_list stmt"""
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[1] + p[2]

    def p_semi_opt(self, p):
        """semi_opt : SEMI
                    | empty
        """
        if len(p) == 2:
            p[0] = p[1]

    def p_semi_small_stmt(self, p):
        """semi_small_stmt : SEMI small_stmt"""
        p[0] = [p[2]]

    def p_simple_stmt(self, p):
        """simple_stmt : small_stmt semi_small_stmt_list semi_opt NEWLINE
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

    _augassign_op = {
        '+=': ast.Add,
        '-=': ast.Sub,
        '*=': ast.Mult,
        '@=': ast.MatMult,
        '/=': ast.Div,
        '%=': ast.Mod,
        '//=': ast.FloorDiv,
        '**=': ast.Pow,
        '^=': ast.BitXor,
        '&=': ast.BitAnd,
        '|=': ast.BitOr,
        '<<=': ast.LShift,
        '>>=': ast.RShift
    }

    def p_expr_stmt(self, p):
        """expr_stmt : testlist_star_expr augassign yield_expr_or_testlist
                     | testlist_star_expr equals_yield_expr_or_testlist_list_opt
                     | testlist equals_yield_expr_or_testlist_list_opt
                     | test_comma_list_opt star_expr comma_test_list equals_yield_expr_or_testlist
                     | test_comma_list_opt star_expr comma_opt test_comma_list_opt equals_yield_expr_or_testlist
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        p1 = [] if p1 is None else p1
        if isinstance(p1, ast.Tuple):
            p1 = [p1]
        for targ in p1:
            store_ctx(targ)
        if lenp == 3:
            if p2 is None and len(p1) == 1:
                load_ctx(p1[0])
                p0 = self.expr(p1[0])
            elif p2 is None:
                assert False
            else:
                list(map(store_ctx, p2[:-1]))
                p0 = ast.Assign(targets=p1 + p2[:-1],
                                value=p2[-1],
                                lineno=self.lineno,
                                col_offset=self.col)
        elif lenp == 4:
            op = self._augassign_op[p2]
            if op is None:
                self._parse_error('operation {0!r} not supported'.format(p2), 
                                  self.currloc(lineno=p.lineno, column=p.lexpos))
            p0 = ast.AugAssign(target=p1[0], op=op(), value=p[3],
                               lineno=self.lineno, col_offset=self.col)
        elif lenp == 5 or lenp == 6:
            if lenp == 5:
                targs, rhs = p[3], p[4][0]
            else:
                targs, rhs = (p[4] or []), p[5][0]
            store_ctx(p2)
            for targ in targs:
                store_ctx(targ)
            p1.append(p2)
            p1.extend(targs)
            p1 = [ast.Tuple(elts=p1,
                            ctx=ast.Store(),
                            lineno=self.lineno,
                            col_offset=self.col)]
            p0 = ast.Assign(targets=p1,
                            value=rhs,
                            lineno=self.lineno,
                            col_offset=self.col)
        else:
            assert False
        p[0] = p0

    def p_test_comma(self, p):
        """test_comma : test COMMA"""
        p[0] = [p[1]]

    def p_comma_opt(self, p):
        """comma_opt : COMMA
                     | empty
        """
        if len(p) == 2:
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
        """testlist_star_expr : test_or_star_expr comma_test_or_star_expr_list comma_opt
                              | test_or_star_expr comma_opt
        """
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = [p1]
        elif p2 == ',':
            p0 = [ast.Tuple(elts=[p1],
                            ctx=ast.Load(),
                            lineno=self.lineno,
                            col_offset=self.col)]
        else:
            p0 = [ast.Tuple(elts=[p1] + p2,
                            ctx=ast.Load(),
                            lineno=self.lineno,
                            col_offset=self.col)]
        p[0] = p0

    def p_augassign(self, p):
        """augassign : PLUSEQUAL
                     | MINUSEQUAL
                     | TIMESEQUAL
                     | ATEQUAL
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
        p[0] = [p[2]]

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
        p0 = ast.Raise(exc=exc,
                       cause=cause,
                       lineno=self.lineno,
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
            if p[1] == '*':
                p[1] = [ast.alias(name='*', asname=None)]
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
        p[0] = ast.ImportFrom(module=mod,
                              names=p[3],
                              level=lvl,
                              lineno=self.lineno,
                              col_offset=self.col)

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
        """dotted_name : NAME
                       | NAME period_name_list
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_comma_name(self, p):
        """comma_name : COMMA NAME"""
        p[0] = [p[2]]

    def p_global_stmt(self, p):
        """global_stmt : GLOBAL NAME comma_name_list_opt"""
        p2, p3 = p[2], p[3]
        names = [p2]
        if p3 is not None:
            names += p3
        p[0] = ast.Global(names=names, lineno=self.lineno, col_offset=self.col)

    def p_nonlocal_stmt(self, p):
        """nonlocal_stmt : NONLOCAL NAME comma_name_list_opt"""
        p2, p3 = p[2], p[3]
        names = [p2]
        if p3 is not None:
            names += p3
        p[0] = ast.Nonlocal(names=names,
                            lineno=self.lineno,
                            col_offset=self.col)

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
        p0 = ast.Assert(test=p2,
                        msg=p3,
                        lineno=self.lineno,
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
                         | async_stmt
        """
        p[0] = p[1]

    def p_elif_part(self, p):
        """elif_part : ELIF test COLON suite"""
        p[0] = [ast.If(test=p[2],
                       body=p[4],
                       orelse=[],
                       lineno=self.lineno,
                       col_offset=self.col)]

    def p_else_part(self, p):
        """else_part : ELSE COLON suite"""
        p[0] = p[3]

    def p_if_stmt(self, p):
        """if_stmt : IF test COLON suite elif_part_list_opt
                   | IF test COLON suite elif_part_list_opt else_part
        """
        lastif = ast.If(test=p[2],
                        body=p[4],
                        orelse=[],
                        lineno=self.lineno,
                        col_offset=self.col)
        p0 = [lastif]
        p5 = p[5]
        p6 = p[6] if len(p) > 6 else []
        if p5 is not None:
            for elseif in p5:
                lastif.orelse.append(elseif)
                lastif = elseif
        lastif.orelse = p6
        p[0] = p0

    def p_while_stmt(self, p):
        """while_stmt : WHILE test COLON suite
                      | WHILE test COLON suite else_part
        """
        p5 = p[5] if len(p) > 5 else []
        p[0] = [ast.While(test=p[2],
                          body=p[4],
                          orelse=p5,
                          lineno=self.lineno,
                          col_offset=self.col)]

    def p_for_stmt(self, p):
        """for_stmt : FOR exprlist IN testlist COLON suite
                    | FOR exprlist IN testlist COLON suite else_part
        """
        p2 = p[2]
        p7 = p[7] if len(p) > 7 else []
        if len(p2) == 1:
            p2 = p2[0]
            store_ctx(p2)
        else:
            for x in p2:
                store_ctx(x)
            p2 = ast.Tuple(elts=p2,
                           ctx=ast.Store(),
                           lineno=self.lineno,
                           col_offset=self.col)
        p[0] = [ast.For(target=p2,
                        iter=p[4],
                        body=p[6],
                        orelse=p7,
                        lineno=self.lineno,
                        col_offset=self.col)]

    def p_async_for_stmt(self, p):
        """async_for_stmt : ASYNC for_stmt"""
        f = p[2][0]
        p[0] = [ast.AsyncFor(**f.__dict__)]

    def p_except_part(self, p):
        """except_part : except_clause COLON suite"""
        p0 = p[1]
        p0.body = p[3]
        p[0] = [p0]

    def p_finally_part(self, p):
        """finally_part : FINALLY COLON suite"""
        p[0] = p[3]

    def p_try_stmt(self, p):
        """try_stmt : TRY COLON suite except_part_list else_part finally_part_opt
                    | TRY COLON suite except_part_list finally_part_opt
                    | TRY COLON suite finally_part
        """
        lenp = len(p)
        t = ast.Try(body=p[3], lineno=self.lineno, col_offset=self.col)
        if lenp == 7:
            p5, p6 = p[5], p[6]
            t.handlers = p[4]
            t.orelse = [] if p5 is None else p5
            t.finalbody = [] if p6 is None else p6
        elif lenp == 6:
            p5 = p[5]
            t.handlers = p[4]
            t.orelse = []
            t.finalbody = [] if p5 is None else p5
        else:
            t.handlers = []
            t.orelse = []
            t.finalbody = p[4]
        p[0] = [t]

    def p_with_stmt(self, p):
        """with_stmt : WITH with_item COLON suite
                     | WITH with_item comma_with_item_list COLON suite
        """
        p2, p3 = [p[2]], p[3]
        if len(p) == 5:
            body = p[4]
        else:
            p2 += p3
            body = p[5]
        p[0] = [ast.With(items=p2,
                         body=body,
                         lineno=self.lineno,
                         col_offset=self.col)]

    def p_async_with_stmt(self, p):
        """async_with_stmt : ASYNC with_stmt"""
        w = p[2][0]
        p[0] = [ast.AsyncWith(**w.__dict__)]

    def p_as_expr(self, p):
        """as_expr : AS expr"""
        p2 = p[2]
        store_ctx(p2)
        p[0] = p2

    def p_with_item(self, p):
        """with_item : test
                     | test as_expr
        """
        p2 = p[2] if len(p) > 2 else None
        p[0] = ast.withitem(context_expr=p[1], optional_vars=p2)

    def p_comma_with_item(self, p):
        """comma_with_item : COMMA with_item"""
        p[0] = [p[2]]

    def p_except_clause(self, p):
        """except_clause : EXCEPT
                         | EXCEPT test as_name_opt
        """
        if len(p) == 2:
            p0 = ast.ExceptHandler(type=None,
                                   name=None,
                                   lineno=self.lineno,
                                   col_offset=self.col)
        else:
            p0 = ast.ExceptHandler(type=p[2],
                                   name=p[3],
                                   lineno=self.lineno,
                                   col_offset=self.col)
        p[0] = p0

    def p_async_stmt(self, p):
        """async_stmt : async_funcdef
                      | async_with_stmt 
                      | async_for_stmt
        """
        p[0] = p[1]

    def p_suite(self, p):
        """suite : simple_stmt
                 | NEWLINE INDENT stmt_list DEDENT
        """
        p[0] = p[1] if len(p) == 2 else p[3]

    def p_test(self, p):
        """test : or_test
                | or_test IF or_test ELSE test
                | lambdef
        """
        if len(p) == 2:
            p0 = p[1]
        else:
            p0 = ast.IfExp(test=p[3],
                           body=p[1],
                           orelse=p[5],
                           lineno=self.lineno,
                           col_offset=self.col)
        p[0] = p0

    def p_test_nocond(self, p):
        """test_nocond : or_test
                       | lambdef_nocond
        """
        p[0] = p[1]

    def p_lambdef(self, p):
        """lambdef : LAMBDA varargslist_opt COLON test"""
        p2, p4 = p[2], p[4]
        if p2 is None:
            args = ast.arguments(args=[],
                                 vararg=None,
                                 kwonlyargs=[],
                                 kw_defaults=[],
                                 kwarg=None,
                                 defaults=[])
        else:
            args = p2
        p0 = ast.Lambda(args=args,
                        body=p4,
                        lineno=self.lineno,
                        col_offset=self.col)
        p[0] = p0

    def p_lambdef_nocond(self, p):
        """lambdef_nocond : LAMBDA varargslist_opt COLON test_nocond"""
        assert False

    def p_or_test(self, p):
        """or_test : and_test or_and_test_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        elif len(p2) == 2:
            p0 = ast.BoolOp(op=p2[0],
                            values=[p[1], p2[1]],
                            lineno=self.lineno,
                            col_offset=self.col)
        else:
            p0 = ast.BoolOp(op=p2[0],
                            values=[p[1]] + p2[1::2],
                            lineno=self.lineno,
                            col_offset=self.col)
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
            p0 = ast.BoolOp(op=p2[0],
                            values=[p[1], p2[1]],
                            lineno=self.lineno,
                            col_offset=self.col)
        else:
            p0 = ast.BoolOp(op=p2[0],
                            values=[p[1]] + p2[1::2],
                            lineno=self.lineno,
                            col_offset=self.col)
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
            p0 = ast.UnaryOp(op=ast.Not(),
                             operand=p[2],
                             lineno=self.lineno,
                             col_offset=self.col)
        p[0] = p0

    def p_comparison(self, p):
        """comparison : expr comp_op_expr_list_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = p[1]
        else:
            p0 = ast.Compare(left=p[1],
                             ops=p2[::2],
                             comparators=p2[1::2],
                             lineno=self.lineno,
                             col_offset=self.col)
        p[0] = p0

    def p_comp_op_expr(self, p):
        """comp_op_expr : comp_op expr"""
        p[0] = [p[1], p[2]]

    _comp_ops = {
        '<': ast.Lt,
        '>': ast.Gt,
        '==': ast.Eq,
        '>=': ast.GtE,
        '<=': ast.LtE,
        '!=': ast.NotEq,
        'in': ast.In,
        ('not', 'in'): ast.NotIn,
        'is': ast.Is,
        ('is', 'not'): ast.IsNot
    }

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
        p[0] = ast.Starred(value=p[2],
                           ctx=ast.Load(),
                           lineno=self.lineno,
                           col_offset=self.col)

    def _binop_combine(self, p1, p2):
        """Combines binary operations"""
        if p2 is None:
            p0 = p1
        elif isinstance(p2, ast.BinOp):
            p2.left = p1
            p0 = p2
        elif isinstance(p2, Sequence) and isinstance(p2[0], ast.BinOp):
            p0 = p2[0]
            p0.left = p1
            for bop in p2[1:]:
                bop.left = p0
                p0 = bop
        else:
            p0 = p1 + p2
        return p0

    def p_expr(self, p):
        """expr : xor_expr
                | xor_expr pipe_xor_expr_list
        """
        p[0] = self._binop_combine(p[1], p[2] if len(p) > 2 else None)

    def p_pipe_xor_expr(self, p):
        """pipe_xor_expr : PIPE xor_expr"""
        p[0] = [ast.BinOp(left=None,
                          op=ast.BitOr(),
                          right=p[2],
                          lineno=self.lineno,
                          col_offset=self.col)]

    def p_xor_expr(self, p):
        """xor_expr : and_expr xor_and_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_xor_and_expr(self, p):
        """xor_and_expr : XOR and_expr"""
        p[0] = [ast.BinOp(left=None,
                          op=ast.BitXor(),
                          right=p[2],
                          lineno=self.lineno,
                          col_offset=self.col)]

    def p_and_expr(self, p):
        """and_expr : shift_expr ampersand_shift_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_ampersand_shift_expr(self, p):
        """ampersand_shift_expr : AMPERSAND shift_expr"""
        p[0] = [ast.BinOp(left=None,
                          op=ast.BitAnd(),
                          right=p[2],
                          lineno=self.lineno,
                          col_offset=self.col)]

    def p_shift_expr(self, p):
        """shift_expr : arith_expr shift_arith_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_shift_arith_expr(self, p):
        """shift_arith_expr : LSHIFT arith_expr
                            | RSHIFT arith_expr
        """
        op = ast.LShift() if p[1] == '<<' else ast.RShift()
        p[0] = [ast.BinOp(left=None,
                          op=op,
                          right=p[2],
                          lineno=self.lineno,
                          col_offset=self.col)]

    def p_arith_expr(self, p):
        """arith_expr : term
                      | term pm_term_list
        """
        p2 = p[2] if len(p) > 2 else None
        if p2 is None:
            p0 = p[1]
        elif len(p2) == 2:
            p0 = ast.BinOp(left=p[1],
                           op=p2[0],
                           right=p2[1],
                           lineno=self.lineno,
                           col_offset=self.col)
        else:
            left = p[1]
            for op, right in zip(p2[::2], p2[1::2]):
                left = ast.BinOp(left=left,
                                 op=op,
                                 right=right,
                                 lineno=self.lineno,
                                 col_offset=self.col)
            p0 = left
        p[0] = p0

    _term_binops = {
        '+': ast.Add,
        '-': ast.Sub,
        '*': ast.Mult,
        '@': ast.MatMult,
        '/': ast.Div,
        '%': ast.Mod,
        '//': ast.FloorDiv
    }

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
            p0 = ast.BinOp(left=p[1],
                           op=p2[0],
                           right=p2[1],
                           lineno=self.lineno,
                           col_offset=self.col)
        else:
            left = p[1]
            for op, right in zip(p2[::2], p2[1::2]):
                left = ast.BinOp(left=left,
                                 op=op,
                                 right=right,
                                 lineno=self.lineno,
                                 col_offset=self.col)
            p0 = left
        p[0] = p0

    def p_op_factor(self, p):
        """op_factor : TIMES factor
                     | AT factor
                     | DIVIDE factor
                     | MOD factor
                     | DOUBLEDIV factor
        """
        op = self._term_binops[p[1]]
        if op is None:
            self._parse_error('operation {0!r} not supported'.format(p[1]), 
                              self.currloc(lineno=p.lineno, column=p.lexpos))
        p[0] = [op(), p[2]]

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
            p0 = ast.UnaryOp(op=op,
                             operand=p[2],
                             lineno=self.lineno,
                             col_offset=self.col)
        p[0] = p0

    def p_power(self, p):
        """power : atom_expr
                 | atom_expr POW factor
        """
        lenp = len(p)
        p1 = p[1]
        if lenp == 2:
            p0 = p1
        elif lenp == 4:
            # actual power rule
            p0 = ast.BinOp(left=p1,
                           op=ast.Pow(),
                           right=p[3],
                           lineno=self.lineno,
                           col_offset=self.col)
        p[0] = p0

    def p_yield_expr_or_testlist_comp(self, p):
        """yield_expr_or_testlist_comp : yield_expr
                                       | testlist_comp
        """
        p[0] = p[1]

    def _list_or_elts_if_not_real_tuple(self, x):
        if isinstance(x, ast.Tuple) and not (hasattr(x, '_real_tuple') and \
                                             x._real_tuple):
            rtn = x.elts
        else:
            rtn = [x]
        return rtn

    @docstring_by_version(
        v34="""atom_expr : atom trailer_list_opt""",
        v35=\
        """atom_expr : atom trailer_list_opt
                     | AWAIT atom trailer_list_opt
        """
        )
    def p_atom_expr(self, p):
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
                                   lineno=self.lineno,
                                   col_offset=self.col)
            elif isinstance(trailer, Mapping):
                p0 = ast.Call(func=leader,
                              lineno=self.lineno,
                              col_offset=self.col, **trailer)
            elif isinstance(trailer, str):
                if trailer == '?':
                    p0 = xonsh_help(leader, lineno=self.lineno, col=self.col)
                elif trailer == '??':
                    p0 = xonsh_superhelp(leader,
                                         lineno=self.lineno,
                                         col=self.col)
                else:
                    p0 = ast.Attribute(value=leader,
                                       attr=trailer,
                                       ctx=ast.Load(),
                                       lineno=self.lineno,
                                       col_offset=self.col)
            else:
                assert False
            leader = p0
        if lenp == 4:
            p0 = ast.Await(value=p0, ctx=ast.Load(), lineno=self.lineno, 
                           col_offset=self.col)
        p[0] = p0

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
                | REGEXPATH
                | DOLLAR_NAME
                | DOLLAR_LBRACE test RBRACE
                | DOLLAR_LPAREN subproc RPAREN
                | DOLLAR_LBRACKET subproc RBRACKET
        """
        p1 = p[1]
        if len(p) == 2:
            # plain-old atoms
            bt = '`'
            if isinstance(p1, (ast.Num, ast.Str, ast.Bytes)):
                pass
            elif p1 == 'True':
                p1 = ast.NameConstant(value=True,
                                      lineno=self.lineno,
                                      col_offset=self.col)
            elif p1 == 'False':
                p1 = ast.NameConstant(value=False,
                                      lineno=self.lineno,
                                      col_offset=self.col)
            elif p1 == 'None':
                p1 = ast.NameConstant(value=None,
                                      lineno=self.lineno,
                                      col_offset=self.col)
            elif p1 == '...':
                p1 = ast.Ellipsis(lineno=self.lineno, col_offset=self.col)
            elif p1.startswith(bt) and p1.endswith(bt):
                p1 = ast.Str(s=p1.strip(bt),
                             lineno=self.lineno,
                             col_offset=self.col)
                p1 = xonsh_regexpath(p1, lineno=self.lineno, col=self.col)
            elif p1.startswith('$'):
                p1 = self._envvar_by_name(p1[1:],
                                          lineno=self.lineno,
                                          col=self.col)
            else:
                p1 = ast.Name(id=p1,
                              ctx=ast.Load(),
                              lineno=self.lineno,
                              col_offset=self.col)
            p[0] = p1
            return
        p2 = p[2]
        if p2 is None:
            # empty container atoms
            if p1 == '(':
                p0 = ast.Tuple(elts=[],
                               ctx=ast.Load(),
                               lineno=self.lineno,
                               col_offset=self.col)
            elif p1 == '[':
                p0 = ast.List(elts=[],
                              ctx=ast.Load(),
                              lineno=self.lineno,
                              col_offset=self.col)
            elif p1 == '{':
                p0 = ast.Dict(keys=[],
                              values=[],
                              ctx=ast.Load(),
                              lineno=self.lineno,
                              col_offset=self.col)
            else:
                assert False
        elif p1 == '(':
            # filled, possible group container tuple atoms
            if isinstance(p2, ast.AST):
                p0 = p2
                p0._real_tuple = True
            elif len(p2) == 1 and isinstance(p2[0], ast.AST):
                p0 = p2[0]
            else:
                assert False
        elif p1 == '[':
            if isinstance(p2, ast.GeneratorExp):
                p0 = ast.ListComp(elt=p2.elt,
                                  generators=p2.generators,
                                  lineno=p2.lineno,
                                  col_offset=p2.col_offset)
            else:
                if isinstance(p2, ast.Tuple):
                    if hasattr(p2, '_real_tuple') and p2._real_tuple:
                        elts = [p2]
                    else:
                        elts = p2.elts
                else:
                    elts = [p2]
                p0 = ast.List(elts=elts,
                              ctx=ast.Load(),
                              lineno=self.lineno,
                              col_offset=self.col)
        elif p1 == '{':
            p0 = p2
        elif p1.startswith('$'):
            p0 = self._dollar_rules(p)
        else:
            assert False
        p[0] = p0

    def p_string_literal(self, p):
        """string_literal : STRING"""
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
        """number : NUMBER"""
        p[0] = ast.Num(n=eval(p[1]), lineno=self.lineno, col_offset=self.col)

    def p_testlist_comp(self, p):
        """testlist_comp : test_or_star_expr comp_for
                         | test_or_star_expr comma_opt
                         | test_or_star_expr comma_test_or_star_expr_list comma_opt
        """
        p1, p2 = p[1], p[2]
        if len(p) == 3:
            if p2 is None:
                # split out grouping parentheses.
                p0 = p1
            elif p2 == ',':
                p0 = ast.Tuple(elts=[p1],
                               ctx=ast.Load(),
                               lineno=self.lineno,
                               col_offset=self.col)
            elif 'comps' in p2:
                p0 = ast.GeneratorExp(elt=p1,
                                      generators=p2['comps'],
                                      lineno=self.lineno,
                                      col_offset=self.col)
            else:
                assert False
        elif len(p) == 4:
            p0 = ast.Tuple(elts=[p1],
                           ctx=ast.Load(),
                           lineno=self.lineno,
                           col_offset=self.col)
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
                   | DOUBLE_QUESTION
                   | QUESTION
        """
        p1 = p[1]
        p2 = p[2] if len(p) > 2 else None
        if p1 == '[':
            p0 = [p2]
        elif p1 == '(':
            p0 = [p2 or dict(args=[], keywords=[], starargs=None, kwargs=None)]
        elif p1 == '.':
            p0 = [p2]
        elif p1 == '?' or p1 == '??':
            p0 = [p1]
        else:
            assert False
        p[0] = p0

    def p_subscriptlist(self, p):
        """subscriptlist : subscript comma_subscript_list_opt comma_opt"""
        p1, p2 = p[1], p[2]
        if p2 is not None:
            p1.value = ast.Tuple(elts=[p1.value] + [x.value for x in p2],
                                 ctx=ast.Load(),
                                 lineno=self.lineno,
                                 col_offset=self.col)
        p[0] = p1

    def p_comma_subscript(self, p):
        """comma_subscript : COMMA subscript"""
        p[0] = [p[2]]

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
        """exprlist : expr_or_star_expr comma_expr_or_star_expr_list comma_opt
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
        """testlist : test comma_test_list COMMA
                    | test comma_test_list
                    | test COMMA
                    | test
        """
        lenp = len(p)
        p1 = p[1]
        if lenp > 2:
            if isinstance(p1, ast.Tuple) and \
                    (hasattr(p1, '_real_tuple') and p1._real_tuple):
                p1 = ast.Tuple(elts=[p1],
                               ctx=ast.Load(),
                               lineno=self.lineno,
                               col_offset=self.col)
            else:
                p1 = ensure_has_elts(p1,
                                     lineno=self.lineno,
                                     col_offset=self.col)
            p2 = p[2] if lenp > 2 else []
            p2 = [] if p2 == ',' else p2
            p1.elts += p2
        p[0] = p1

    @docstring_by_version(
        v34="""item : test COLON test""",
        v35=\
        """item : test COLON test
                | POW expr
        """,
        )
    def p_item(self, p):
        lenp = len(p)
        if lenp == 4: 
            p0 = [p[1], p[3]]
        elif lenp == 3:
            p0 = [None, p[2]]
        else:
            assert False
        p[0] = p0

    def p_comma_item(self, p):
        """comma_item : COMMA item"""
        p[0] = p[2]

    def p_dictorsetmaker(self, p):
        """dictorsetmaker : item comp_for
                          | test_or_star_expr comp_for
                          | testlist
                          | test_or_star_expr comma_opt
                          | test_or_star_expr comma_test_or_star_expr_list comma_opt
                          | test COLON testlist
                          | item comma_item_list comma_opt
                          | test COLON test comma_item_list comma_opt
        """
        p1 = p[1]
        lenp = len(p)
        if lenp == 2:
            elts = self._list_or_elts_if_not_real_tuple(p1)
            p0 = ast.Set(elts=elts, ctx=ast.Load(), lineno=self.lineno,
                         col_offset=self.col)
        elif lenp == 3:
            p2 = p[2]
            if p2 is None or p2 == ',':
                elts = self._list_or_elts_if_not_real_tuple(p1)
                p0 = ast.Set(elts=elts, ctx=ast.Load(), lineno=self.lineno,
                            col_offset=self.col)
            else:
                comps = p2.get('comps', [])
                if isinstance(p1, list) and len(p1) == 2:
                    p0 = ast.DictComp(key=p1[0], value=p1[1], generators=comps,
                                      lineno=self.lineno, col_offset=self.col)
                else:
                    p0 = ast.SetComp(elt=p1, generators=comps, lineno=self.lineno,
                                     col_offset=self.col)
        elif lenp == 4:
            p2, p3 = p[2], p[3]
            if isinstance(p1, list) and len(p1) == 2:
                cls = ast.Dict
                keys = [p1[0]]
                vals = [p1[1]]
                for k, v in zip(p2[::2], p2[1::2]):
                    keys.append(k)
                    vals.append(v)
                p0 = ast.Dict(keys=keys, values=vals, ctx=ast.Load(), lineno=self.lineno,
                              col_offset=self.col)
            elif p2 == ':':
                keys = [p1]
                vals = self._list_or_elts_if_not_real_tuple(p3)
                p0 = ast.Dict(keys=keys, values=vals, ctx=ast.Load(), lineno=self.lineno,
                              col_offset=self.col)
            elif isinstance(p1, ast.AST):
                elts = [p1] + p2
                p0 = ast.Set(elts=elts, ctx=ast.Load(), lineno=self.lineno,
                             col_offset=self.col)
            else:
                assert False
        elif lenp == 6:
            p4 = p[4]
            keys = [p1]
            vals = [p[3]]
            for k, v in zip(p4[::2], p4[1::2]):
                keys.append(k)
                vals.append(v)
            p0 = ast.Dict(keys=keys, values=vals, ctx=ast.Load(), lineno=self.lineno,
                          col_offset=self.col)
        else:
            assert False
        p[0] = p0

    def p_classdef(self, p):
        """classdef : CLASS NAME func_call_opt COLON suite"""
        p3 = p[3]
        b, kw = ([], []) if p3 is None else (p3['args'], p3['keywords'])
        c = ast.ClassDef(name=p[2],
                         bases=b,
                         keywords=kw,
                         starargs=None,
                         kwargs=None,
                         body=p[5],
                         decorator_list=[],
                         lineno=self.lineno,
                         col_offset=self.col)
        p[0] = [c]

    def _set_arg(self, args, arg, ensure_kw=False):
        if isinstance(arg, ast.keyword):
            args['keywords'].append(arg)
        elif ensure_kw:
            if VER_MAJOR_MINOR <= VER_3_4:
                args['kwargs'] = arg
            elif VER_MAJOR_MINOR >= VER_3_5:
                args['keywords'].append(ast.keyword(arg=None, value=arg))
        else:
            args['args'].append(arg)

    #
    # arglist rule had significant changes
    #
    if VER_3_5 <= VER_MAJOR_MINOR:
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
    else:  # Python v3.4
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
                kwkey = 'keywords' if VER_MAJOR_MINOR >= VER_3_5 else 'kwargs'
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

    if VER_MAJOR_MINOR <= VER_3_4:
        def p_argument_comma(self, p):
            """argument_comma : argument COMMA"""
            p[0] = [p[1]]

    def p_comma_argument(self, p):
        """comma_argument : COMMA argument"""
        p[0] = [p[2]]

    @docstring_by_version(
        v34 = \
        """argument : test
                    | test comp_for
                    | test EQUALS test
        """, 
        v35 = \
        """argument : test_or_star_expr
                    | test comp_for
                    | test EQUALS test
                    | POW test
                    | TIMES test
        """,
        )
    def p_argument(self, p):
        # v3.4 Notes
        # Really [keyword '='] test
        # The reason that keywords are test nodes instead of NAME is that using
        # NAME results in an ambiguity.
        #
        # v3.5 Notes
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
                                      lineno=self.lineno, col_offset=self.col)
        elif lenp == 4:
            p0 = ast.keyword(arg=p1.id, value=p[3])
        else:
            assert False
        p[0] = p0

    def p_comp_iter(self, p):
        """comp_iter : comp_for
                     | comp_if
        """
        p[0] = p[1]

    def p_comp_for(self, p):
        """comp_for : FOR exprlist IN or_test comp_iter_opt"""
        targs, it, p5 = p[2], p[4], p[5]
        if len(targs) == 1:
            targ = targs[0]
        else:
            targ = ensure_has_elts(targs, lineno=self.lineno,
                                   col_offset=self.col)
        store_ctx(targ)
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

    def p_yield_expr(self, p):
        """yield_expr : YIELD yield_arg_opt"""
        p2 = p[2]
        if p2 is None:
            p0 = ast.Yield(value=p2, lineno=self.lineno, col_offset=self.col)
        elif p2['from']:
            p0 = ast.YieldFrom(value=p2['val'],
                               lineno=self.lineno,
                               col_offset=self.col)
        else:
            p0 = ast.Yield(value=p2['val'],
                           lineno=self.lineno,
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

    #
    # subprocess
    #

    def _dollar_rules(self, p):
        """These handle the special xonsh $ shell atoms by looking up
        in a special __xonsh_env__ dictionary injected in the __builtin__.
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        col = self.col
        lineno = self.lineno
        if lenp == 3:  # $NAME
            p0 = self._envvar_by_name(p2, lineno=lineno, col=col)
        elif p1 == '${':
            xenv = self._xenv(lineno=lineno, col=col)
            idx = ast.Index(value=p2)
            p0 = ast.Subscript(value=xenv,
                               slice=idx,
                               ctx=ast.Load(),
                               lineno=lineno,
                               col_offset=col)
        elif p1 == '$(':
            p0 = xonsh_call('__xonsh_subproc_captured__', p2,
                            lineno=lineno,
                            col=col)
        elif p1 == '$[':
            p0 = xonsh_call('__xonsh_subproc_uncaptured__', p2,
                            lineno=lineno,
                            col=col)
        else:
            assert False
        return p0

    def _xenv(self, lineno=lineno, col=col):
        """Creates a new xonsh env reference."""
        return ast.Name(id='__xonsh_env__',
                        ctx=ast.Load(),
                        lineno=lineno,
                        col_offset=col)

    def _envvar_by_name(self, var, lineno=None, col=None):
        """Looks up a xonsh variable by name."""
        xenv = self._xenv(lineno=lineno, col=col)
        idx = ast.Index(value=ast.Str(s=var, lineno=lineno, col_offset=col))
        return ast.Subscript(value=xenv,
                             slice=idx,
                             ctx=ast.Load(),
                             lineno=lineno,
                             col_offset=col)

    def _subproc_cliargs(self, args, lineno=None, col=None):
        """Creates an expression for subprocess CLI arguments."""
        cliargs = currlist = empty_list(lineno=lineno, col=col)
        for arg in args:
            action = arg._cliarg_action
            if action == 'append':
                if currlist is None:
                    currlist = empty_list(lineno=lineno, col=col)
                    cliargs = binop(cliargs, ast.Add(), currlist,
                                    lineno=lineno,
                                    col=col)
                currlist.elts.append(arg)
            elif action == 'extend':
                cliargs = binop(cliargs, ast.Add(), arg,
                                lineno=lineno,
                                col=col)
                currlist = None
            elif action == 'splitlines':
                sl = call_split_lines(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), sl, lineno=lineno, col=col)
                currlist = None
            elif action == 'ensure_list':
                x = ensure_list_from_str_or_list(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), x, lineno=lineno, col=col)
                currlist = None
            else:
                raise ValueError("action not understood: " + action)
            del arg._cliarg_action
        return cliargs

    def p_pipe(self, p):
        """pipe : PIPE
                | WS PIPE
                | PIPE WS
                | WS PIPE WS
        """
        p1 = p[1]
        if len(p) > 2 and len(p1.strip()) == 0:
            p1 = p[2]
        p[0] = ast.Str(s=p1, lineno=self.lineno, col_offset=self.col)

    def p_subproc(self, p):
        """subproc : subproc_atoms
                   | subproc_atoms WS
                   | subproc AMPERSAND
                   | subproc pipe subproc_atoms
                   | subproc pipe subproc_atoms WS
        """
        lineno = self.lineno
        col = self.col
        lenp = len(p)
        p1 = p[1]
        if lenp == 2:
            p0 = [self._subproc_cliargs(p1, lineno=lineno, col=col)]
        elif p[2] == '&':
            p0 = p1 + [ast.Str(s=p[2], lineno=lineno, col_offset=col)]
        elif lenp == 3:
            p0 = [self._subproc_cliargs(p1, lineno=lineno, col=col)]
        else:
            if len(p1) > 1 and hasattr(p1[-2], 's') and p1[-2].s != '|':
                msg = 'additional redirect following non-pipe redirect'
                self._parse_error(msg, self.currloc(lineno=lineno, column=col))
            cliargs = self._subproc_cliargs(p[3], lineno=lineno, col=col)
            p0 = p1 + [p[2], cliargs]
        # return arguments list
        p[0] = p0

    def p_subproc_atoms(self, p):
        """subproc_atoms : subproc_atom
                         | subproc_atoms WS subproc_atom
        """
        p1 = p[1]
        if len(p) < 4:
            p1 = [p1]
        else:
            p1.append(p[3])
        p[0] = p1

    def p_subproc_atom(self, p):
        """subproc_atom : subproc_arg
                        | string_literal
                        | REGEXPATH
                        | DOLLAR_NAME
                        | GT
                        | LT
                        | RSHIFT
                        | IOREDIRECT
                        | AT_LPAREN test RPAREN
                        | DOLLAR_LBRACE test RBRACE
                        | DOLLAR_LPAREN subproc RPAREN
                        | DOLLAR_LBRACKET subproc RBRACKET
        """
        lenp = len(p)
        p1 = p[1]
        if lenp == 2:
            if isinstance(p1, str):
                p0 = ast.Str(s=p1, lineno=self.lineno, col_offset=self.col)
                bt = '`'
                if p1.startswith(bt) and p1.endswith(bt):
                    p0.s = p1.strip(bt)
                    p0 = xonsh_regexpath(p0, lineno=self.lineno, col=self.col)
                    p0._cliarg_action = 'extend'
                elif '*' in p1:
                    p0 = xonsh_call('__xonsh_glob__',
                                    args=[p0],
                                    lineno=self.lineno,
                                    col=self.col)
                    p0._cliarg_action = 'extend'
                elif p1.startswith('$'):
                    p0 = self._envvar_by_name(p1[1:],
                                              lineno=self.lineno,
                                              col=self.col)
                    p0 = xonsh_call('__xonsh_ensure_list_of_strs__', [p0],
                                    lineno=self.lineno,
                                    col=self.col)
                    p0._cliarg_action = 'extend'
                else:
                    p0.s = os.path.expanduser(p0.s)
                    p0._cliarg_action = 'append'
            elif isinstance(p1, ast.AST):
                p0 = p1
                p0._cliarg_action = 'append'
            else:
                assert False
        elif p1 == '@(':
            p0 = xonsh_call('__xonsh_ensure_list_of_strs__', [p[2]],
                            lineno=self.lineno,
                            col=self.col)
            p0._cliarg_action = 'extend'
        elif p1 == '${':
            xenv = self._xenv(lineno=self.lineno, col=self.col)
            idx = ast.Index(value=p[2])
            p0 = ast.Subscript(value=xenv,
                               slice=idx,
                               ctx=ast.Load(),
                               lineno=self.lineno,
                               col_offset=self.col)
            p0._cliarg_action = 'append'
        elif p1 == '$(':
            p0 = xonsh_call('__xonsh_subproc_captured__',
                            args=p[2],
                            lineno=self.lineno,
                            col=self.col)
            p0._cliarg_action = 'splitlines'
        elif p1 == '$[':
            p0 = xonsh_call('__xonsh_subproc_uncaptured__',
                            args=p[2],
                            lineno=self.lineno,
                            col=self.col)
            p0._cliarg_action = 'splitlines'
        else:
            assert False
        p[0] = p0

    def p_subproc_arg(self, p):
        """subproc_arg : subproc_arg_part
                       | subproc_arg subproc_arg_part
        """
        # This glues the string together after parsing
        p1 = p[1]
        if len(p) == 2:
            p0 = p1
        else:
            p0 = p1 + p[2]
        p[0] = p0

    def p_subproc_arg_part(self, p):
        """subproc_arg_part : NAME
                            | TILDE
                            | PERIOD
                            | DIVIDE
                            | MINUS
                            | PLUS
                            | COLON
                            | AT
                            | EQUALS
                            | TIMES
                            | POW
                            | MOD
                            | XOR
                            | DOUBLEDIV
                            | ELLIPSIS
                            | NONE
                            | TRUE
                            | FALSE
                            | NUMBER
                            | STRING
        """
        # Many tokens cannot be part of this list, such as $, ', ", ()
        # Use a string atom instead.
        p[0] = p[1]

    #
    # Helpers
    #

    def p_empty(self, p):
        'empty : '
        p[0] = None

    def p_error(self, p):
        if p is None:
            self._parse_error('no further code', None)
        elif p.type == 'ERRORTOKEN':
            if isinstance(p.value, BaseException):
                raise p.value
            else:
                self._parse_error(p.value, self.currloc(lineno=p.lineno,
                                                        column=p.lexpos))
        else:
            msg = 'code: {0}'.format(p.value),
            self._parse_error(msg, self.currloc(lineno=p.lineno,
                                                column=p.lexpos))
