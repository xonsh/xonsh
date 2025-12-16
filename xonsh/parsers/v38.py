"""Implements the xonsh parser for Python v3.8."""

import xonsh.parsers.ast as ast
from xonsh.parsers.base import store_ctx
from xonsh.parsers.v36 import Parser as ThreeSixParser


class Parser(ThreeSixParser):
    """A Python v3.8 compliant parser for the xonsh language."""

    def __init__(
        self,
        yacc_optimize=True,
        yacc_table="xonsh.parser_table",
        yacc_debug=False,
        outputdir=None,
    ):
        """Parameters
        ----------
        yacc_optimize : bool, optional
            Set to false when unstable and true when parser is stable.
        yacc_table : str, optional
            Parser module used when optimized.
        yacc_debug : debug, optional
            Dumps extra debug info.
        outputdir : str or None, optional
            The directory to place generated tables within.
        """
        # Rule creation and modification *must* take place before super()
        opt_rules = ["testlist_star_expr"]
        for rule in opt_rules:
            self._opt_rule(rule)
        list_rules = ["comma_namedexpr_test_or_star_expr"]
        for rule in list_rules:
            self._list_rule(rule)
        tok_rules = ["colonequal"]
        for rule in tok_rules:
            self._tok_rule(rule)
        super().__init__(
            yacc_optimize=yacc_optimize,
            yacc_table=yacc_table,
            yacc_debug=yacc_debug,
            outputdir=outputdir,
        )

    def _set_posonly_args_def(self, argmts, vals):
        for v in vals:
            argmts.posonlyargs.append(v["arg"])
            d = v["default"]
            if d is not None:
                argmts.defaults.append(d)
            elif argmts.defaults:
                self._set_error("non-default argument follows default argument")

    def _set_posonly_args(self, p0, p1, p2, p3):
        if p2 is None and p3 is None:
            # x
            p0.posonlyargs.append(p1)
        elif p2 is not None and p3 is None:
            # x=42
            p0.posonlyargs.append(p1)
            p0.defaults.append(p2)
        elif p2 is None and p3 is not None:
            # x, y and x, y=42
            p0.posonlyargs.append(p1)
            self._set_posonly_args_def(p0, p3)
        else:
            # x=42, y=42
            p0.posonlyargs.append(p1)
            p0.defaults.append(p2)
            self._set_posonly_args_def(p0, p3)

    def p_parameters(self, p):
        """parameters : LPAREN typedargslist_opt RPAREN"""
        p2 = p[2]
        if p2 is None:
            p2 = ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            )
        p[0] = p2

    def p_typedargslist_kwarg(self, p):
        """typedargslist : POW tfpdef"""
        p[0] = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[2],
            defaults=[],
        )

    def p_typedargslist_times4_tfpdef(self, p):
        """typedargslist : TIMES tfpdef comma_pow_tfpdef_opt"""
        # *args, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[3],
            defaults=[],
        )
        self._set_var_args(p0, p[2], None)
        p[0] = p0

    def p_typedargslist_times4_comma(self, p):
        """typedargslist : TIMES comma_pow_tfpdef"""
        # *, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[2],
            defaults=[],
        )
        p[0] = p0

    def p_typedargslist_times5_tdpdef(self, p):
        """typedargslist : TIMES tfpdef comma_tfpdef_list comma_pow_tfpdef_opt"""
        # *args, x, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[4],
            defaults=[],
        )
        self._set_var_args(p0, p[2], p[3])  # *args
        p[0] = p0

    def p_typedargslist_times5_comma(self, p):
        """typedargslist : TIMES comma_tfpdef_list comma_pow_tfpdef_opt"""
        # *, x, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[3],
            defaults=[],
        )
        self._set_var_args(p0, None, p[2])  # *args
        p[0] = p0

    def p_typedargslist_t5(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt"""
        # x
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_typedargslist_t7(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt POW tfpdef"""
        # x, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[6],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_typedargslist_t8(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list_opt"""
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_typedargslist_t10(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt COMMA POW vfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[9],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], None)
        p[0] = p0

    def p_typedargslist_t11(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list COMMA POW tfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[10],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_typedargslist_t12(self, p):
        """
        typedargslist : posonlyargslist comma_opt
                      | posonlyargslist COMMA typedargslist
        """
        if len(p) == 4:
            p0 = p[3]
            p0.posonlyargs = p[1].posonlyargs
            # If posonlyargs contain default arguments, all following arguments must have defaults.
            if p[1].defaults and (len(p[3].defaults) != len(p[3].args)):
                self._set_error("non-default argument follows default argument")
        else:
            p0 = p[1]
        p[0] = p0

    def p_posonlyargslist(self, p):
        """
        posonlyargslist : tfpdef equals_test_opt COMMA DIVIDE
                        | tfpdef equals_test_opt comma_tfpdef_list COMMA DIVIDE"""
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        if p[3] == ",":
            self._set_posonly_args(p0, p[1], p[2], None)
        else:
            self._set_posonly_args(p0, p[1], p[2], p[3])
        p[0] = p0

    def p_varargslist_kwargs(self, p):
        """varargslist : POW vfpdef"""
        p[0] = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[2],
            defaults=[],
        )

    def p_varargslist_times4(self, p):
        """varargslist : TIMES vfpdef_opt comma_pow_vfpdef_opt"""
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[3],
            defaults=[],
        )
        self._set_var_args(p0, p[2], None)
        p[0] = p0

    def p_varargslist_times5(self, p):
        """varargslist : TIMES vfpdef_opt comma_vfpdef_list comma_pow_vfpdef_opt"""
        # *args, x, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[4],
            defaults=[],
        )
        self._set_var_args(p0, p[2], p[3])  # *args
        p[0] = p0

    def p_varargslist_v5(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt"""
        # x
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_varargslist_v7(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt POW vfpdef"""
        # x, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[6],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_varargslist_v8(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list_opt"""
        # x, *args
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_varargslist_v10(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt COMMA POW vfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[9],
            defaults=[],
        )
        self._set_regular_args(p0, *p[1:5])
        self._set_var_args(p0, p[6], None)
        p[0] = p0

    def p_varargslist_v11(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list COMMA POW vfpdef"""
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[10],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_varargslist_t12(self, p):
        """
        varargslist : posonlyvarargslist comma_opt
                    | posonlyvarargslist COMMA varargslist
        """
        if len(p) == 4:
            p0 = p[3]
            p0.posonlyargs = p[1].posonlyargs
            # If posonlyargs contain default arguments, all following arguments must have defaults.
            if p[1].defaults and (len(p[3].defaults) != len(p[3].args)):
                self._set_error("non-default argument follows default argument")
        else:
            p0 = p[1]
        p[0] = p0

    def p_posonlyvarargslist(self, p):
        """
        posonlyvarargslist : vfpdef equals_test_opt COMMA DIVIDE
                           | vfpdef equals_test_opt comma_vfpdef_list COMMA DIVIDE"""
        p0 = ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        )
        if p[3] == ",":
            self._set_posonly_args(p0, p[1], p[2], None)
        else:
            self._set_posonly_args(p0, p[1], p[2], p[3])
        p[0] = p0

    def p_lambdef(self, p):
        """lambdef : lambda_tok varargslist_opt COLON test"""
        p1, p2, p4 = p[1], p[2], p[4]
        if p2 is None:
            args = ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            )
        else:
            args = p2
        p0 = ast.Lambda(args=args, body=p4, lineno=p1.lineno, col_offset=p1.lexpos)
        p[0] = p0

    def p_decorated(self, p):
        """decorated : decorators classdef_or_funcdef"""
        p1, p2 = p[1], p[2]
        targ = p2[0]
        targ.decorator_list = p1
        # async functions take the col number of the 'def', unless they are
        # decorated, in which case they have the col of the 'async'. WAT?
        if hasattr(targ, "_async_tok"):
            targ.col_offset = targ._async_tok.lexpos
            del targ._async_tok
        p[0] = p2

    def p_argument_colonequal(self, p):
        """argument : test COLONEQUAL test"""
        p1 = p[1]
        store_ctx(p1)
        p[0] = ast.NamedExpr(
            target=p1, value=p[3], lineno=p1.lineno, col_offset=p1.col_offset
        )

    def p_namedexpr_test(self, p):
        """
        namedexpr_test : test
                       | test COLONEQUAL test
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p1 = p[1]
            store_ctx(p1)
            p[0] = ast.NamedExpr(
                target=p1, value=p[3], lineno=p1.lineno, col_offset=p1.col_offset
            )

    def p_namedexpr_test_or_star_expr(self, p):
        """
        namedexpr_test_or_star_expr : namedexpr_test
                                    | star_expr
        """
        p[0] = p[1]

    def p_comma_namedexpr_test_or_star_expr(self, p):
        """comma_namedexpr_test_or_star_expr : COMMA namedexpr_test_or_star_expr"""
        p[0] = [p[2]]

    def p_testlist_comp_comp(self, p):
        """testlist_comp : namedexpr_test_or_star_expr comp_for"""
        super().p_testlist_comp_comp(p)

    def p_testlist_comp_comma(self, p):
        """testlist_comp : namedexpr_test_or_star_expr comma_opt"""
        super().p_testlist_comp_comma(p)

    def p_testlist_comp_many(self, p):
        """testlist_comp : namedexpr_test_or_star_expr comma_namedexpr_test_or_star_expr_list comma_opt"""
        super().p_testlist_comp_many(p)

    def p_elif_part(self, p):
        """elif_part : ELIF namedexpr_test COLON suite"""
        super().p_elif_part(p)

    def p_if_stmt(self, p):
        """
        if_stmt : if_tok namedexpr_test COLON suite elif_part_list_opt
                | if_tok namedexpr_test COLON suite elif_part_list_opt else_part
        """
        super().p_if_stmt(p)

    def p_while_stmt(self, p):
        """
        while_stmt : WHILE namedexpr_test COLON suite
                   | WHILE namedexpr_test COLON suite else_part
        """
        super().p_while_stmt(p)

    def p_return_stmt(self, p):
        """return_stmt : return_tok testlist_star_expr_opt"""
        p1 = p[1]
        p[0] = ast.Return(
            value=p[2][0] if p[2] is not None else None,
            lineno=p1.lineno,
            col_offset=p1.lexpos,
        )

    def p_yield_arg_testlist(self, p):
        # remove pre 3.8 grammar
        pass

    def p_yield_arg_testlist_star_expr(self, p):
        """yield_arg : testlist_star_expr"""
        p[0] = {"from": False, "val": p[1][0]}
