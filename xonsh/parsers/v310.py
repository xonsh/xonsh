"""Handles changes since PY310

handle
- import-alias requiring lineno
"""

import ast

from xonsh.parsers.v39 import Parser as ThreeNineParser
from xonsh.ply.ply import yacc


class Parser(ThreeNineParser):
    def p_import_from_post_times(self, p):
        """import_from_post : TIMES"""
        p[0] = [ast.alias(name=p[1], asname=None, **self.get_line_cols(p, 1))]

    def p_import_as_name(self, p):
        """import_as_name : NAME as_name_opt"""
        self.p_dotted_as_name(p)

    def p_dotted_as_name(self, p: yacc.YaccProduction):
        """dotted_as_name : dotted_name as_name_opt"""
        alias_idx = 2
        p[0] = ast.alias(
            name=p[1], asname=p[alias_idx], **self.get_line_cols(p, alias_idx)
        )

    @staticmethod
    def get_line_cols(p: yacc.YaccProduction, idx: int):
        line_no, end_line_no = p.linespan(idx)
        col_offset, end_col_offset = p.lexspan(idx)
        return dict(
            lineno=line_no,
            end_lineno=end_line_no,
            col_offset=col_offset,
            end_col_offset=end_col_offset,
        )
