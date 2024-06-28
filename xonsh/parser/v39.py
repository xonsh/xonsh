"""Handles changes since PY39

handle
- removal of ast.Index and ast.ExtSlice -- https://bugs.python.org/issue34822 -- more info
    `at<https://docs.python.org/3/whatsnew/3.9.html?highlight=simplified%20ast%20subscription#changes-in-the-python-api>`_.
"""

import ast

from xonsh.parsers.base import Index
from xonsh.parsers.v38 import Parser as ThreeEightParser


class Parser(ThreeEightParser):
    def p_subscript_test(self, p):
        """subscript : test"""
        p1 = p[1]
        p[0] = Index(value=p1)

    def p_subscriptlist(self, p):
        """subscriptlist : subscript comma_subscript_list_opt comma_opt"""

        p1, p2 = p[1], p[2]
        is_subscript = False

        if p2 is not None:
            if isinstance(p1, Index):
                p1 = p1.value
                is_subscript = True
            if any(isinstance(p, Index) for p in p2):
                is_subscript = True

            after_comma = [p.value if isinstance(p, Index) else p for p in p2]
            if (
                isinstance(p1, ast.Slice)
                or any([isinstance(x, ast.Slice) for x in after_comma])
                or is_subscript
            ):
                p1 = Index(
                    value=ast.Tuple(
                        [p1] + after_comma,
                        ctx=ast.Load(),
                        lineno=p1.lineno,
                        col_offset=p1.col_offset,
                    )
                )
            else:
                p1.value = ast.Tuple(
                    elts=[p1.value] + [x.value for x in after_comma],
                    ctx=ast.Load(),
                    lineno=p1.lineno,
                    col_offset=p1.col_offset,
                )
        p[0] = p1
