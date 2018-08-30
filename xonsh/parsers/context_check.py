import ast
import keyword
import collections

_all_keywords = frozenset(keyword.kwlist)


def _not_assignable(x, augassign=False):
    """
    If ``x`` represents a value that can be assigned to, return ``None``.
    Otherwise, return a string describing the object.  For use in generating
    meaningful syntax errors.
    """
    if augassign and isinstance(x, (ast.Tuple, ast.List)):
        return "literal"
    elif isinstance(x, (ast.Tuple, ast.List)):
        if len(x.elts) == 0:
            return "()"
        for i in x.elts:
            res = _not_assignable(i)
            if res is not None:
                return res
    elif isinstance(x, (ast.Set, ast.Dict, ast.Num, ast.Str, ast.Bytes)):
        return "literal"
    elif isinstance(x, ast.Call):
        return "function call"
    elif isinstance(x, ast.Lambda):
        return "lambda"
    elif isinstance(x, (ast.BoolOp, ast.BinOp, ast.UnaryOp)):
        return "operator"
    elif isinstance(x, ast.IfExp):
        return "conditional expression"
    elif isinstance(x, ast.ListComp):
        return "list comprehension"
    elif isinstance(x, ast.DictComp):
        return "dictionary comprehension"
    elif isinstance(x, ast.SetComp):
        return "set comprehension"
    elif isinstance(x, ast.GeneratorExp):
        return "generator expression"
    elif isinstance(x, ast.Compare):
        return "comparison"
    elif isinstance(x, ast.Name) and x.id in _all_keywords:
        return "keyword"
    elif isinstance(x, ast.NameConstant):
        return "keyword"


_loc = collections.namedtuple("_loc", ["lineno", "column"])


def check_contexts(tree):
    c = ContextCheckingVisitor()
    c.visit(tree)
    if c.error is not None:
        e = SyntaxError(c.error[0])
        e.loc = _loc(c.error[1], c.error[2])
        raise e


class ContextCheckingVisitor(ast.NodeVisitor):
    def __init__(self):
        self.error = None

    def visit_Delete(self, node):
        for i in node.targets:
            err = _not_assignable(i)
            if err is not None:
                msg = "can't delete {}".format(err)
                self.error = msg, i.lineno, i.col_offset
                break

    def visit_Assign(self, node):
        for i in node.targets:
            err = _not_assignable(i)
            if err is not None:
                msg = "can't assign to {}".format(err)
                self.error = msg, i.lineno, i.col_offset
                break

    def visit_AugAssign(self, node):
        err = _not_assignable(node.target, True)
        if err is not None:
            msg = "illegal target for augmented assignment: {}".format(err)
            self.error = msg, node.target.lineno, node.target.col_offset
