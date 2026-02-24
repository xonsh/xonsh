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
                self._set_error(f"'{p[1]}' is an invalid prefix before 'import', expected 'lazy'")
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
