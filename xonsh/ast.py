"""The xonsh abstract syntax tree node."""
from __future__ import unicode_literals, print_function
from ast import Module, Num, Expr, Str, Bytes, UnaryOp, UAdd, USub, Invert, \
    BinOp, Add, Sub, Mult, Div, FloorDiv, Mod, Pow, Compare, Lt, Gt, LtE, \
    GtE, Eq, NotEq, In, NotIn, Is, IsNot, Not, BoolOp, Or, And, Subscript, \
    Index, Load, Slice, List, Tuple, Set, Dict, AST, NameConstant, Ellipsis, \
    Name, GeneratorExp, Store, comprehension, ListComp, SetComp, DictComp, \
    Assign, AugAssign, BitXor, BitAnd, BitOr, LShift, RShift, Assert, Delete, \
    Del, Pass, Raise, Import, alias, ImportFrom, Continue, Break, Yield, \
    YieldFrom, Return, IfExp, Lambda, arguments, arg, Call, keyword, \
    Attribute, Global, Nonlocal, If, While, For, withitem, With, Try, \
    ExceptHandler, FunctionDef, ClassDef, Starred, NodeTransformer

from xonsh.tools import subproc_line

def leftmostname(node):
    """Attempts to find the first name in the tree."""
    if isinstance(node, Name):
        rtn = node.id
    elif isinstance(node, (Str, Bytes)):
        rtn = node.s
    elif isinstance(node, (BinOp, Compare)):
        rtn = leftmostname(node.left)
    elif isinstance(node, (Attribute, Subscript)):
        rtn = leftmostname(node.value)
    else:
        rtn = None
    return rtn

class CtxAwareTransformer(NodeTransformer):
    """Transforms a xonsh AST based to use subprocess calls when 
    the first name in an expression statement is not known in the context.
    This assumes that the expression statement is instead parseable as
    a subprocess.
    """

    def __init__(self, pasrer):
        """Parameters
        ----------
        parser : xonsh.Parser
            A parse instance to try to parse suprocess statements with.
        """
        super(CtxAwareTransformer, self).__init__()
        self.parser = parser
        self.input = None
        self.contexts = []

    def ctxvisit(self, node, input, ctx):
        """Transforms the node in a context-dependent way.

        Parameters
        ----------
        node : ast.AST
            A syntax tree to transform.
        input : str
            The input code in string format.
        ctx : dict
            The root context to use.

        Returns
        -------
        node : ast.AST
            The transformed node.
        """
        self.lines = input.splitlines()
        self.contexts = [ctx]
        node = self.visit(node)
        del self.lines, self.contexts
        return node
    
    def visit_Expr(self, node):
        lname = leftmostname(node)
        inscope = False
        for ctx in self.contexts[::-1]:
            if lname in ctx:
                inscope = True 
                break
        if inscope:
            return node
        newline = subproc_line(self.lines[node.lineno])
        try:
            node = self.parser.parse(newline)
        except SyntaxError as e:
            pass
        return node


