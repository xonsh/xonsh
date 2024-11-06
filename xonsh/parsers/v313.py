# type: ignore
# TODO: remove line above once mypy understands the match statement

"""Handles changes since PY313

handle
- import-alias requiring lineno
- match statement
"""

from ast import match_case
from ast import parse as pyparse

from xonsh.parsers import ast
from xonsh.parsers.ast import xonsh_call
from xonsh.parsers.base import (
    RE_STRINGPREFIX,
    del_ctx,
    ensure_has_elts,
    lopen_loc,
    store_ctx,
)
from xonsh.parsers.fstring_adaptor import FStringAdaptor
from xonsh.parsers.v310 import Parser as ThreeTenParser


class Parser(ThreeTenParser):
    def p_eval_input(self, p):
        """eval_input : testlist newlines_opt"""
        p1 = p[1]
        expression = ast.Expression(body=p1)
        expression.lineno = p1.lineno
        expression.col_offset = p1.col_offset
        p[0] = expression

    def p_pm_term(self, p):
        """
        pm_term : plus_tok term
                | minus_tok term
        """
        p1 = p[1]
        op = self._term_binops[p1.value]()
        op.lineno = p1.lineno
        op.col_offset = p1.lexpos
        p[0] = [op, p[2]]

    def p_atom_lbrace(self, p):
        """atom : lbrace_tok dictorsetmaker_opt RBRACE"""
        p1, p2 = p[1], p[2]
        p1, p1_tok = p1.value, p1
        if p2 is None:
            p0 = ast.Dict(
                keys=[],
                values=[],
                lineno=self.lineno,
                col_offset=self.col,
            )
            p0.ctx = ast.Load()
        else:
            p0 = p2
            p0.lineno, p0.col_offset = p1_tok.lineno, p1_tok.lexpos
        p[0] = p0

    # case blocks
    def p_case_block(self, p):
        """
        case_block : case_tok patterns COLON suite
                   | case_tok patterns IF test COLON suite
        """

        loc = self.get_line_cols(p, 1)
        match list(p):
            case [_, _, pattern, _, suite]:
                p[0] = match_case(pattern=pattern, body=suite)
                p[0].lineno = loc["lineno"]
                p[0].end_lineno = loc["end_lineno"]
                p[0].col_offset = loc["col_offset"]
                p[0].end_col_offset = loc["end_col_offset"]
            case [_, _, pattern, _, guard, _, suite]:
                p[0] = match_case(pattern=pattern, body=suite, guard=guard)
                p[0].lineno = loc["lineno"]
                p[0].end_lineno = loc["end_lineno"]
                p[0].col_offset = loc["col_offset"]
                p[0].end_col_offset = loc["end_col_offset"]
            case _:
                raise AssertionError()

    def p_string_literal(self, p):
        """string_literal : string_tok"""
        p1 = p[1]
        prefix = RE_STRINGPREFIX.match(p1.value).group().lower()
        if "p" in prefix and "f" in prefix:
            new_pref = prefix.replace("p", "")
            value_without_p = new_pref + p1.value[len(prefix) :]
            try:
                s = pyparse(value_without_p).body[0].value
            except SyntaxError:
                s = None
            if s is None:
                try:
                    s = FStringAdaptor(
                        value_without_p, new_pref, filename=self.lexer.fname
                    ).run()
                except SyntaxError as e:
                    self._set_error(
                        str(e), self.currloc(lineno=p1.lineno, column=p1.lexpos)
                    )
            s = ast.increment_lineno(s, p1.lineno - 1)
            p[0] = xonsh_call(
                "__xonsh__.path_literal", [s], lineno=p1.lineno, col=p1.lexpos
            )
        elif "p" in prefix:
            value_without_p = prefix.replace("p", "") + p1.value[len(prefix) :]
            s = ast.const_str(
                s=ast.literal_eval(value_without_p),
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
            p[0] = xonsh_call(
                "__xonsh__.path_literal", [s], lineno=p1.lineno, col=p1.lexpos
            )
        elif "f" in prefix:
            try:
                s = pyparse(p1.value).body[0].value
            except SyntaxError:
                s = None
            if s is None:
                try:
                    s = FStringAdaptor(
                        p1.value, prefix, filename=self.lexer.fname
                    ).run()
                except SyntaxError as e:
                    self._set_error(
                        str(e), self.currloc(lineno=p1.lineno, column=p1.lexpos)
                    )
            s = ast.increment_lineno(s, p1.lineno - 1)
            if "r" in prefix:
                s.is_raw = True
            p[0] = s
        else:
            s = ast.literal_eval(p1.value)
            is_bytes = "b" in prefix
            is_raw = "r" in prefix
            cls = ast.const_bytes if is_bytes else ast.const_str
            p[0] = cls(s=s, lineno=p1.lineno, col_offset=p1.lexpos)
            p[0].is_raw = is_raw

    def p_atom_expr_await(self, p):
        """atom_expr : await_tok atom trailer_list_opt"""
        p0 = self.apply_trailers(p[2], p[3])
        p1 = p[1]
        p0 = ast.Await(value=p0, lineno=p1.lineno, col_offset=p1.lexpos)
        p0.ctx = ast.Load()
        p[0] = p0

    #
    # For normal assignments, additional restrictions enforced
    # by the interpreter
    #
    def p_del_stmt(self, p):
        """del_stmt : del_tok exprlist"""
        p1 = p[1]
        p2 = p[2]
        for targ in p2:
            del_ctx(targ)
        p0 = ast.Delete(targets=p2, lineno=p1.lineno, col_offset=p1.lexpos)
        p[0] = p0

    #
    # Dict or set maker
    #
    def p_dictorsetmaker_t6(self, p):
        """dictorsetmaker : test COLON test comma_item_list comma_opt"""
        p1, p4 = p[1], p[4]
        keys = [p1]
        vals = [p[3]]
        for k, v in zip(p4[::2], p4[1::2]):
            keys.append(k)
            vals.append(v)
        lineno, col = lopen_loc(p1)
        p[0] = ast.Dict(keys=keys, values=vals, lineno=lineno, col_offset=col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_i4(self, p):
        """dictorsetmaker : item comma_item_list comma_opt"""
        p1, p2 = p[1], p[2]
        keys = [p1[0]]
        vals = [p1[1]]
        for k, v in zip(p2[::2], p2[1::2]):
            keys.append(k)
            vals.append(v)
        lineno, col = lopen_loc(p1[0] or p1[1])
        p[0] = ast.Dict(keys=keys, values=vals, lineno=lineno, col_offset=col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_t4_dict(self, p):
        """dictorsetmaker : test COLON testlist"""
        keys = [p[1]]
        vals = self._list_or_elts_if_not_real_tuple(p[3])
        lineno, col = lopen_loc(p[1])
        p[0] = ast.Dict(keys=keys, values=vals, lineno=lineno, col_offset=col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_item_comma(self, p):
        """dictorsetmaker : item comma_opt"""
        p1 = p[1]
        keys = [p1[0]]
        vals = [p1[1]]
        lineno, col = lopen_loc(p1[0] or p1[1])
        p[0] = ast.Dict(keys=keys, values=vals, lineno=lineno, col_offset=col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_t4_set(self, p):
        """dictorsetmaker : test_or_star_expr comma_test_or_star_expr_list comma_opt"""
        p[0] = ast.Set(elts=[p[1]] + p[2], lineno=self.lineno, col_offset=self.col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_test_comma(self, p):
        """dictorsetmaker : test_or_star_expr comma_opt"""
        elts = self._list_or_elts_if_not_real_tuple(p[1])
        p[0] = ast.Set(elts=elts, lineno=self.lineno, col_offset=self.col)
        p[0].ctx = ast.Load()

    def p_dictorsetmaker_testlist(self, p):
        """dictorsetmaker : testlist"""
        elts = self._list_or_elts_if_not_real_tuple(p[1])
        p[0] = ast.Set(elts=elts, lineno=self.lineno, col_offset=self.col)
        p[0].ctx = ast.Load()

    def p_op_factor(self, p):
        """
        op_factor : times_tok factor
                    | at_tok factor
                    | divide_tok factor
                    | mod_tok factor
                    | doublediv_tok factor
        """
        p1 = p[1]
        op = self._term_binops[p1.value]
        if op is None:
            self._set_error(
                f"operation {p1!r} not supported",
                self.currloc(lineno=p.lineno, column=p.lexpos),
            )
        op = op()
        op.lineno = p1.lineno
        op.col_offset = p1.lexpos
        p[0] = [op, p[2]]

    def p_comp_for(self, p):
        """comp_for : FOR exprlist IN or_test comp_iter_opt"""
        targs, it, p5 = p[2], p[4], p[5]
        if len(targs) == 1:
            targ = targs[0]
        else:
            targ = ensure_has_elts(targs)
        store_ctx(targ)
        comp = ast.comprehension(target=targ, iter=it, ifs=[], is_async=0)
        comps = [comp]
        p0 = {"comps": comps}
        if p5 is not None:
            comps += p5.get("comps", [])
            comp.ifs += p5.get("if", [])
        p[0] = p0
