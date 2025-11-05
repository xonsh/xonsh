from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import TYPE_CHECKING, NamedTuple

from xonsh_rd_parser import Parser as RDParser

if TYPE_CHECKING:
    from xonsh_rd_parser import Token


class Location(NamedTuple):
    """Location in a file."""

    fname: str
    lineno: int
    column: int


class Lexer:
    src = ""
    tokens = ()

    def input(self, src: str):
        self.src = src

    @property
    def parser(self):
        return RDParser(self.src)

    def __iter__(self) -> Iterator[Token]:
        self.tokens = self.parser.tokens(tolerant=True)
        return iter(self.tokens)

    def reset(self):
        self.tokens = ()

    def subproc_toks(
        self, line: str, mincol=-1, maxcol=-1, returnline=False, greedy=False
    ) -> str | None:
        """Encapsulates tokens in a source code line in a uncaptured
        subprocess ![] starting at a minimum column. If there are no tokens
        (ie in a comment line) this returns None. If greedy is True, it will encapsulate
        normal parentheses. Greedy is False by default.
        """
        self.input(line)
        return self.parser.subproc_toks(
            mincol=mincol, maxcol=maxcol, returnline=returnline, greedy=greedy
        )


class Parser:
    """A parser interface for the Ruff parser."""

    def __init__(self, **_):
        self.lexer = Lexer()

    def parse(self, s, filename="<code>", mode="exec", **_):
        """Returns an abstract syntax tree of xonsh code."""

        self._source = s

        try:
            tree = RDParser(s, file_name=filename).parse()
        except SyntaxError as ex:
            # this gets used by excer to try out subproc parsing
            ex.loc = Location(ex.filename, ex.lineno, ex.offset)
            raise ex
        # hack for getting modes right
        if mode == "single":
            assert isinstance(tree, ast.Module)
            tree = ast.Interactive(body=tree.body)
        elif mode == "eval":
            assert isinstance(tree, ast.Module)
            assert len(tree.body) == 1
            tree = ast.Expression(body=tree.body[0].value)
        return tree
