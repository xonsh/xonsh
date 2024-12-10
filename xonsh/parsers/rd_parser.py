import ast

from xonsh_rd_parser import lex_string, parse_string


class Lexer:
    src = ""
    tokens = ()

    def input(self, src: str):
        self.src = src

    def __iter__(self):
        self.tokens = lex_string(self.src)
        return iter(self.tokens)

    def reset(self):
        self.tokens = ()


class Parser:
    """A parser interface for the Ruff parser."""

    def __init__(self, **_):
        self.lexer = Lexer()

    def parse(self, s, filename="<code>", mode="exec", **_):
        """Returns an abstract syntax tree of xonsh code."""

        self._source = s
        tree = parse_string(s, file_name=filename)
        # hack for getting modes right
        if mode == "single":
            assert isinstance(tree, ast.Module)
            tree = ast.Interactive(body=tree.body)
        return tree
