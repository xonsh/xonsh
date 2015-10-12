"""The xonsh abstract syntax tree node."""
from ast import Module, Num, Expr, Str, Bytes, UnaryOp, UAdd, USub, Invert, \
    BinOp, Add, Sub, Mult, Div, FloorDiv, Mod, Pow, Compare, Lt, Gt, \
    LtE, GtE, Eq, NotEq, In, NotIn, Is, IsNot, Not, BoolOp, Or, And, Subscript, \
    Load, Slice, List, Tuple, Set, Dict, AST, NameConstant, \
    Name, GeneratorExp, Store, comprehension, ListComp, SetComp, DictComp, \
    Assign, AugAssign, BitXor, BitAnd, BitOr, LShift, RShift, Assert, Delete, \
    Del, Pass, Raise, Import, alias, ImportFrom, Continue, Break, Yield, \
    YieldFrom, Return, IfExp, Lambda, arguments, arg, Call, keyword, \
    Attribute, Global, Nonlocal, If, While, For, withitem, With, Try, \
    ExceptHandler, FunctionDef, ClassDef, Starred, NodeTransformer, \
    Interactive, Expression, dump
from ast import Ellipsis, Index  # pylint:disable=unused-import,redefined-builtin

from xonsh.tools import subproc_toks, VER_3_5, VER_MAJOR_MINOR

if VER_3_5 <= VER_MAJOR_MINOR:
    from ast import MatMult, AsyncFunctionDef, AsyncWith, AsyncFor, Await
else:
    MatMult = AsyncFunctionDef = AsyncWith = AsyncFor = Await = None

STATEMENTS = (FunctionDef, ClassDef, Return, Delete, Assign, AugAssign, For,
              While, If, With, Raise, Try, Assert, Import, ImportFrom, Global,
              Nonlocal, Expr, Pass, Break, Continue)


def leftmostname(node):
    """Attempts to find the first name in the tree."""
    if isinstance(node, Name):
        rtn = node.id
    elif isinstance(node, (BinOp, Compare)):
        rtn = leftmostname(node.left)
    elif isinstance(node, (Attribute, Subscript, Starred, Expr)):
        rtn = leftmostname(node.value)
    elif isinstance(node, Call):
        rtn = leftmostname(node.func)
    elif isinstance(node, (BinOp, Compare)):
        rtn = leftmostname(node.left)
    elif isinstance(node, Assign):
        rtn = leftmostname(node.targets[0])
    elif isinstance(node, (Str, Bytes)):
        # handles case of "./my executable"
        rtn = leftmostname(node.s)
    else:
        rtn = None
    return rtn


class CtxAwareTransformer(NodeTransformer):
    """Transforms a xonsh AST based to use subprocess calls when
    the first name in an expression statement is not known in the context.
    This assumes that the expression statement is instead parseable as
    a subprocess.
    """

    def __init__(self, parser):
        """Parameters
        ----------
        parser : xonsh.Parser
            A parse instance to try to parse suprocess statements with.
        """
        super(CtxAwareTransformer, self).__init__()
        self.parser = parser
        self.input = None
        self.contexts = []
        self.lines = None
        self.mode = None

    def ctxvisit(self, node, inp, ctx, mode='exec'):
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
        self.lines = inp.splitlines()
        self.contexts = [ctx, set()]
        self.mode = mode
        node = self.visit(node)
        del self.lines, self.contexts, self.mode
        return node

    def ctxupdate(self, iterable):
        """Updated the most recent context."""
        self.contexts[-1].update(iterable)

    def ctxadd(self, value):
        """Adds a value the most recent context."""
        self.contexts[-1].add(value)

    def ctxremove(self, value):
        """Removes a value the most recent context."""
        for ctx in reversed(self.contexts):
            if value in ctx:
                ctx.remove(value)
                break

    def try_subproc_toks(self, node):
        """Tries to parse the line of the node as a subprocess."""
        line = self.lines[node.lineno - 1]
        mincol = len(line) - len(line.lstrip())
        maxcol = None if self.mode == 'eval' else node.col_offset
        spline = subproc_toks(line,
                              mincol=mincol,
                              maxcol=maxcol,
                              returnline=False,
                              lexer=self.parser.lexer)
        try:
            newnode = self.parser.parse(spline, mode=self.mode)
            newnode = newnode.body
            if not isinstance(newnode, AST):
                # take the first (and only) Expr
                newnode = newnode[0]
            newnode.lineno = node.lineno
            newnode.col_offset = node.col_offset
        except SyntaxError:
            newnode = node
        return newnode

    def is_in_scope(self, node):
        """Determines whether or not the current node is in scope."""
        lname = leftmostname(node)
        if lname is None:
            return node
        inscope = False
        for ctx in reversed(self.contexts):
            if lname in ctx:
                inscope = True
                break
        return inscope

    def visit_Expression(self, node):
        body = node.body
        inscope = self.is_in_scope(body)
        if not inscope:
            node.body = self.try_subproc_toks(body)
        return node

    def visit_Expr(self, node):
        if self.is_in_scope(node):
            return node
        else:
            newnode = self.try_subproc_toks(node)
            if not isinstance(newnode, Expr):
                newnode = Expr(value=newnode,
                               lineno=node.lineno,
                               col_offset=node.col_offset)
            return newnode

    def visit_Assign(self, node):
        ups = set()
        for targ in node.targets:
            if isinstance(targ, (Tuple, List)):
                ups.update(map(leftmostname, targ.elts))
            elif isinstance(targ, BinOp):
                newnode = self.try_subproc_toks(node)
                if newnode is node:
                    ups.add(leftmostname(targ))
                else:
                    return newnode
            else:
                ups.add(leftmostname(targ))
        self.ctxupdate(ups)
        return node

    def visit_Import(self, node):
        for name in node.names:
            if name.asname is None:
                self.ctxadd(name.name)
            else:
                self.ctxadd(name.asname)
        return node

    def visit_ImportFrom(self, node):
        for name in node.names:
            if name.asname is None:
                self.ctxadd(name.name)
            else:
                self.ctxadd(name.asname)
        return node

    def visit_With(self, node):
        for item in node.items:
            if item.optional_vars is not None:
                self.ctxadd(leftmostname(item.optional_vars))
        self.generic_visit(node)
        return node

    def visit_For(self, node):
        targ = node.target
        if isinstance(targ, (Tuple, List)):
            self.ctxupdate(map(leftmostname, targ.elts))
        else:
            self.ctxadd(leftmostname(targ))
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        self.ctxadd(node.name)
        self.contexts.append(set())
        self.generic_visit(node)
        self.contexts.pop()
        return node

    def visit_ClassDef(self, node):
        self.ctxadd(node.name)
        self.contexts.append(set())
        self.generic_visit(node)
        self.contexts.pop()
        return node

    def visit_Delete(self, node):
        for targ in node.targets:
            if isinstance(targ, Name):
                self.ctxremove(targ.id)
        self.generic_visit(node)
        return node

    def visit_Try(self, node):
        for handler in node.handlers:
            if handler.name is not None:
                self.ctxadd(handler.name)
        self.generic_visit(node)
        return node

    def visit_Global(self, node):
        self.contexts[1].update(node.names)  # contexts[1] is the global ctx
        self.generic_visit(node)
        return node
