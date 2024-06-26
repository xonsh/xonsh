import ast

from xonsh_rd_parser import parse_string


class Parser:
    """A parser interface for the Ruff parser."""

    def __init__(self, **_):
        pass

    def parse(self, s, filename="<code>", mode="exec", **_):
        """Returns an abstract syntax tree of xonsh code."""

        self._source = s
        tree = parse_string(s, filen_name=filename)
        # hack for getting modes right
        if mode == "single":
            assert isinstance(tree, ast.Module)
            tree = ast.Interactive(body=tree.body)
        return tree
