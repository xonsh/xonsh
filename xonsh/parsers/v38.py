# -*- coding: utf-8 -*-
"""Implements the xonsh parser for Python v3.8."""
import xonsh.ast as ast
from xonsh.parsers.v36 import Parser as ThreeSixParser


class Parser(ThreeSixParser):
    """A Python v3.8 compliant parser for the xonsh language."""

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
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
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
