# type: ignore
# TODO: remove line above once mypy understands the match statement

"""Handles changes since PY313

handle
- import-alias requiring lineno
- match statement
"""

from xonsh.parsers import ast
from xonsh.parsers.v313 import Parser as ThreeThirteenParser


class Parser(ThreeThirteenParser):
    def p_import_stmt(self, p):
        """
        import_stmt    : import_name
                       | import_from
                       | NAME import_name
                       | NAME import_from
        """
        if len(p) == 3:
            if p[1] != "lazy":
                self._set_error(
                    f"'{p[1]}' is an invalid prefix before 'import', expected 'lazy'"
                )
            node = p[2]
            lazy = 1
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    self._set_error("lazy from __future__ import is not allowed")
                elif any(alias.name == "*" for alias in node.names):
                    self._set_error("lazy from ... import * is not allowed")
        else:
            node = p[1]
            lazy = 0
        node.is_lazy = lazy
        p[0] = node
    def p_dictorsetmaker_comp(self, p):
        """
        dictorsetmaker : item comp_for
                       | test_or_star_expr comp_for
        """
        p1 = p[1]
        comps = p[2].get("comps", [])

        if isinstance(p1, list) and len(p1) == 2:
            if p1[0] is None:
                p[0] = ast.DictComp(
                    key=p1[1],
                    generators=comps,
                    lineno=self.lineno,
                    col_offset=self.col,
                )
            else:
                p[0] = ast.DictComp(
                    key=p1[0],
                    value=p1[1],
                    generators=comps,
                    lineno=self.lineno,
                    col_offset=self.col,
                )
        else:
            p[0] = ast.SetComp(
                elt=p1, generators=comps, lineno=self.lineno, col_offset=self.col
            )
    def p_argument_test_or_star(self, p):
        """argument : star_expr comp_for
                    | test_or_star_expr"""
        if len(p) == 3:
            p[0] = ast.GeneratorExp(
                elt=p[1],
                generators=p[2].get("comps", []),
                lineno=self.lineno,
                col_offset=self.col,
            )
        else:
            p[0] = p[1]
