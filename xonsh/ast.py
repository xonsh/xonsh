"""Abstract Syntax Tree handler"""
# These are imported into our module namespace for the benefit of parser.py.
# pylint: disable=unused-import
import itertools
import sys

# pylint: enable=unused-import
import textwrap
from ast import (
    AST,
    Add,
    And,
    AnnAssign,
    Assert,
    Assign,
    AsyncFor,
    AsyncFunctionDef,
    AsyncWith,
    Attribute,
    AugAssign,
    Await,
    BinOp,
    BitAnd,
    BitOr,
    BitXor,
    BoolOp,
    Break,
    Call,
    ClassDef,
    Compare,
    Constant,
    Continue,
    Del,
    Delete,
    Dict,
    DictComp,
    Div,
    Eq,
    ExceptHandler,
    Expr,
    Expression,
    ExtSlice,
    FloorDiv,
    For,
    FormattedValue,
    FunctionDef,
    GeneratorExp,
    Global,
    Gt,
    GtE,
    If,
    IfExp,
    Import,
    ImportFrom,
    In,
    Index,
    Interactive,
    Invert,
    Is,
    IsNot,
    JoinedStr,
    Lambda,
    List,
    ListComp,
    Load,
    LShift,
    Lt,
    LtE,
    MatMult,
    Mod,
    Module,
    Mult,
    Name,
    NamedExpr,
    NodeTransformer,
    Nonlocal,
    Not,
    NotEq,
    NotIn,
    Or,
    Pass,
    Pow,
    Raise,
    Return,
    RShift,
    Set,
    SetComp,
    Slice,
    Starred,
    Store,
    Sub,
    Subscript,
    Try,
    Tuple,
    UAdd,
    UnaryOp,
    USub,
    While,
    With,
    Yield,
    YieldFrom,
    alias,
    arg,
    arguments,
    comprehension,
    dump,
    increment_lineno,
    keyword,
    literal_eval,
    walk,
    withitem,
)

from xonsh.built_ins import XSH
from xonsh.tools import find_next_break, get_logical_line, subproc_toks

STATEMENTS = (
    FunctionDef,
    ClassDef,
    Return,
    Delete,
    Assign,
    AugAssign,
    For,
    While,
    If,
    With,
    Raise,
    Try,
    Assert,
    Import,
    ImportFrom,
    Global,
    Nonlocal,
    Expr,
    Pass,
    Break,
    Continue,
    AnnAssign,
)


def const_str(s: str, **kwargs):
    return Constant(value=s, kind="str", **kwargs)


def is_const_str(node):
    return isinstance(node, Constant) and node.kind == "str"


def const_bytes(s: str, **kwargs):
    return Constant(value=s, kind="bytes", **kwargs)


def is_const_bytes(node):
    return isinstance(node, Constant) and node.kind == "bytes"


def const_num(n, **kwargs):
    return Constant(value=n, kind="num", **kwargs)


def is_const_num(node):
    return isinstance(node, Constant) and node.kind == "num"


def const_name(value, **kwargs):
    return Constant(value=value, kind="name", **kwargs)


def is_const_name(node):
    return isinstance(node, Constant) and node.kind == "name"


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
    elif isinstance(node, UnaryOp):
        rtn = leftmostname(node.operand)
    elif isinstance(node, BoolOp):
        rtn = leftmostname(node.values[0])
    elif isinstance(node, Assign):
        rtn = leftmostname(node.targets[0])
    elif isinstance(node, AnnAssign):
        rtn = leftmostname(node.target)
    elif isinstance(node, JoinedStr) or is_const_str(node) or is_const_bytes(node):
        # handles case of "./my executable"
        rtn = leftmostname(node.s)
    elif isinstance(node, Tuple) and len(node.elts) > 0:
        # handles case of echo ,1,2,3
        rtn = leftmostname(node.elts[0])
    else:
        rtn = None
    return rtn


def get_lineno(node, default=0):
    """Gets the lineno of a node or returns the default."""
    return getattr(node, "lineno", default)


def min_line(node):
    """Computes the minimum lineno."""
    node_line = get_lineno(node)
    return min(map(get_lineno, walk(node), itertools.repeat(node_line)))


def max_line(node):
    """Computes the maximum lineno."""
    return max(map(get_lineno, walk(node)))


def get_col(node, default=-1):
    """Gets the col_offset of a node, or returns the default"""
    return getattr(node, "col_offset", default)


def min_col(node):
    """Computes the minimum col_offset."""
    return min(map(get_col, walk(node), itertools.repeat(node.col_offset)))


def max_col(node):
    """Returns the maximum col_offset of the node and all sub-nodes."""
    col = getattr(node, "max_col", None)
    if col is not None:
        return col
    highest = max(walk(node), key=get_col)
    col = highest.col_offset + node_len(highest)
    return col


def node_len(node):
    """The length of a node as a string"""
    val = 0
    for n in walk(node):
        if isinstance(n, Name):
            val += len(n.id)
        elif isinstance(n, Attribute):
            val += 1 + (len(n.attr) if isinstance(n.attr, str) else 0)
        # this may need to be added to for more nodes as more cases are found
    return val


def get_id(node, default=None):
    """Gets the id attribute of a node, or returns a default."""
    return getattr(node, "id", default)


def gather_names(node):
    """Returns the set of all names present in the node's tree."""
    rtn = set(map(get_id, walk(node)))
    rtn.discard(None)
    return rtn


def get_id_ctx(node):
    """Gets the id and attribute of a node, or returns a default."""
    nid = getattr(node, "id", None)
    if nid is None:
        return (None, None)
    return (nid, node.ctx)


def gather_load_store_names(node):
    """Returns the names present in the node's tree in a set of load nodes and
    a set of store nodes.
    """
    load = set()
    store = set()
    for nid, ctx in map(get_id_ctx, walk(node)):
        if nid is None:
            continue
        elif isinstance(ctx, Load):
            load.add(nid)
        else:
            store.add(nid)
    return (load, store)


def has_elts(x):
    """Tests if x is an AST node with elements."""
    return isinstance(x, AST) and hasattr(x, "elts")


def load_attribute_chain(name, lineno=None, col=None):
    """Creates an AST that loads variable name that may (or may not)
    have attribute chains. For example, "a.b.c"
    """
    names = name.split(".")
    node = Name(id=names.pop(0), ctx=Load(), lineno=lineno, col_offset=col)
    for attr in names:
        node = Attribute(
            value=node, attr=attr, ctx=Load(), lineno=lineno, col_offset=col
        )
    return node


def xonsh_call(name, args, lineno=None, col=None):
    """Creates the AST node for calling a function of a given name.
    Functions names may contain attribute access, e.g. __xonsh__.env.
    """
    return Call(
        func=load_attribute_chain(name, lineno=lineno, col=col),
        args=args,
        keywords=[],
        starargs=None,
        kwargs=None,
        lineno=lineno,
        col_offset=col,
    )


def isdescendable(node):
    """Determines whether or not a node is worth visiting. Currently only
    UnaryOp and BoolOp nodes are visited.
    """
    return isinstance(node, (UnaryOp, BoolOp))


def isexpression(node, ctx=None, *args, **kwargs):
    """Determines whether a node (or code string) is an expression, and
    does not contain any statements. The execution context (ctx) and
    other args and kwargs are passed down to the parser, as needed.
    """
    # parse string to AST
    if isinstance(node, str):
        node = node if node.endswith("\n") else node + "\n"
        ctx = XSH.ctx if ctx is None else ctx
        node = XSH.execer.parse(node, ctx, *args, **kwargs)
    # determine if expression-like enough
    if isinstance(node, (Expr, Expression)):
        isexpr = True
    elif isinstance(node, Module) and len(node.body) == 1:
        isexpr = isinstance(node.body[0], (Expr, Expression))
    else:
        isexpr = False
    return isexpr


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
            A parse instance to try to parse subprocess statements with.
        """
        super().__init__()
        self.parser = parser
        self.input = None
        self.contexts = []
        self.lines = None
        self.mode = None
        self._nwith = 0
        self.filename = "<xonsh-code>"
        self.debug_level = 0

    def ctxvisit(self, node, inp, ctx, mode="exec", filename=None, debug_level=0):
        """Transforms the node in a context-dependent way.

        Parameters
        ----------
        node : ast.AST
            A syntax tree to transform.
        inp : str
            The input code in string format.
        ctx : dict
            The root context to use.
        filename : str, optional
            File we are to transform.
        debug_level : int, optional
            Debugging level to use in lexing and parsing.

        Returns
        -------
        node : ast.AST
            The transformed node.
        """
        self.filename = self.filename if filename is None else filename
        self.debug_level = debug_level
        self.lines = inp.splitlines()
        self.contexts = [ctx, set()]
        self.mode = mode
        self._nwith = 0
        node = self.visit(node)
        del self.lines, self.contexts, self.mode
        self._nwith = 0
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

    def try_subproc_toks(self, node, strip_expr=False):
        """Tries to parse the line of the node as a subprocess."""
        line, nlogical, idx = get_logical_line(self.lines, node.lineno - 1)
        if self.mode == "eval":
            mincol = len(line) - len(line.lstrip())
            maxcol = None
        else:
            mincol = max(min_col(node) - 1, 0)
            maxcol = max_col(node)
            if mincol == maxcol:
                maxcol = find_next_break(line, mincol=mincol, lexer=self.parser.lexer)
            elif nlogical > 1:
                maxcol = None
            elif maxcol < len(line) and line[maxcol] == ";":
                pass
            else:
                maxcol += 1
        spline = subproc_toks(
            line,
            mincol=mincol,
            maxcol=maxcol,
            returnline=False,
            lexer=self.parser.lexer,
        )
        if spline is None or spline != f"![{line[mincol:maxcol].strip()}]":
            # failed to get something consistent, try greedy wrap
            spline = subproc_toks(
                line,
                mincol=mincol,
                maxcol=maxcol,
                returnline=False,
                lexer=self.parser.lexer,
                greedy=True,
            )
        if spline is None:
            return node
        try:
            newnode = self.parser.parse(
                spline,
                mode=self.mode,
                filename=self.filename,
                debug_level=(self.debug_level >= 2),
            )
            newnode = newnode.body
            if not isinstance(newnode, AST):
                # take the first (and only) Expr
                newnode = newnode[0]
            increment_lineno(newnode, n=node.lineno - 1)
            newnode.col_offset = node.col_offset
            if self.debug_level >= 1:
                msg = "{0}:{1}:{2}{3} - {4}\n" "{0}:{1}:{2}{3} + {5}"
                mstr = "" if maxcol is None else ":" + str(maxcol)
                msg = msg.format(self.filename, node.lineno, mincol, mstr, line, spline)
                print(msg, file=sys.stderr)
        except SyntaxError:
            newnode = node
        if strip_expr and isinstance(newnode, Expr):
            newnode = newnode.value
        return newnode

    def is_in_scope(self, node):
        """Determines whether or not the current node is in scope."""
        names, store = gather_load_store_names(node)
        names -= store
        if not names:
            return True
        inscope = False
        for ctx in reversed(self.contexts):
            names -= ctx
            if not names:
                inscope = True
                break
        return inscope

    #
    # Replacement visitors
    #

    def visit_Expression(self, node):
        """Handle visiting an expression body."""
        if isdescendable(node.body):
            node.body = self.visit(node.body)
        body = node.body
        inscope = self.is_in_scope(body)
        if not inscope:
            node.body = self.try_subproc_toks(body)
        return node

    def visit_Expr(self, node):
        """Handle visiting an expression."""
        if isdescendable(node.value):
            node.value = self.visit(node.value)  # this allows diving into BoolOps
        if self.is_in_scope(node) or isinstance(node.value, Lambda):
            return node
        else:
            newnode = self.try_subproc_toks(node)
            if not isinstance(newnode, Expr):
                newnode = Expr(
                    value=newnode, lineno=node.lineno, col_offset=node.col_offset
                )
                if hasattr(node, "max_lineno"):
                    newnode.max_lineno = node.max_lineno
                    newnode.max_col = node.max_col
            return newnode

    def visit_UnaryOp(self, node):
        """Handle visiting an unary operands, like not."""
        if isdescendable(node.operand):
            node.operand = self.visit(node.operand)
        operand = node.operand
        inscope = self.is_in_scope(operand)
        if not inscope:
            node.operand = self.try_subproc_toks(operand, strip_expr=True)
        return node

    def visit_BoolOp(self, node):
        """Handle visiting an boolean operands, like and/or."""
        for i in range(len(node.values)):
            val = node.values[i]
            if isdescendable(val):
                val = node.values[i] = self.visit(val)
            inscope = self.is_in_scope(val)
            if not inscope:
                node.values[i] = self.try_subproc_toks(val, strip_expr=True)
        return node

    def visit_comprehension(self, node):
        """Handles visiting list comprehensions, set comprehensions,
        dictionary comprehensions, and generator expressions."""
        return node  # do not descend into any comprehensions

    #
    # Context aggregator visitors
    #

    def visit_Assign(self, node):
        """Handle visiting an assignment statement."""
        ups = set()
        for targ in node.targets:
            if isinstance(targ, (Tuple, List)):
                ups.update(leftmostname(elt) for elt in targ.elts)
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

    def visit_AnnAssign(self, node):
        """Handle visiting an annotated assignment statement."""
        self.ctxadd(leftmostname(node.target))
        return node

    def visit_Import(self, node):
        """Handle visiting a import statement."""
        for name in node.names:
            if name.asname is None:
                self.ctxadd(name.name)
            else:
                self.ctxadd(name.asname)
        return node

    def visit_ImportFrom(self, node):
        """Handle visiting a "from ... import ..." statement."""
        for name in node.names:
            if name.asname is None:
                self.ctxadd(name.name)
            else:
                self.ctxadd(name.asname)
        return node

    def visit_With(self, node):
        """Handle visiting a with statement."""
        for item in node.items:
            if item.optional_vars is not None:
                self.ctxupdate(gather_names(item.optional_vars))
        self._nwith += 1
        self.generic_visit(node)
        self._nwith -= 1
        return node

    def visit_For(self, node):
        """Handle visiting a for statement."""
        targ = node.target
        self.ctxupdate(gather_names(targ))
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        """Handle visiting a function definition."""
        self.ctxadd(node.name)
        self.contexts.append(set())
        args = node.args
        argchain = [args.args, args.kwonlyargs]
        if args.vararg is not None:
            argchain.append((args.vararg,))
        if args.kwarg is not None:
            argchain.append((args.kwarg,))
        self.ctxupdate(a.arg for a in itertools.chain.from_iterable(argchain))
        self.generic_visit(node)
        self.contexts.pop()
        return node

    def visit_ClassDef(self, node):
        """Handle visiting a class definition."""
        self.ctxadd(node.name)
        self.contexts.append(set())
        self.generic_visit(node)
        self.contexts.pop()
        return node

    def visit_Delete(self, node):
        """Handle visiting a del statement."""
        for targ in node.targets:
            if isinstance(targ, Name):
                self.ctxremove(targ.id)
        self.generic_visit(node)
        return node

    def visit_Try(self, node):
        """Handle visiting a try statement."""
        for handler in node.handlers:
            if handler.name is not None:
                self.ctxadd(handler.name)
        self.generic_visit(node)
        return node

    def visit_Global(self, node):
        """Handle visiting a global statement."""
        self.contexts[1].update(node.names)  # contexts[1] is the global ctx
        self.generic_visit(node)
        return node


def pdump(s, **kwargs):
    """performs a pretty dump of an AST node."""
    if isinstance(s, AST):
        s = dump(s, **kwargs).replace(",", ",\n")
    openers = "([{"
    closers = ")]}"
    lens = len(s) + 1
    if lens == 1:
        return s
    i = min(s.find(o) % lens for o in openers)
    if i == lens - 1:
        return s
    closer = closers[openers.find(s[i])]
    j = s.rfind(closer)
    if j == -1 or j <= i:
        return s[: i + 1] + "\n" + textwrap.indent(pdump(s[i + 1 :]), " ")
    pre = s[: i + 1] + "\n"
    mid = s[i + 1 : j]
    post = "\n" + s[j:]
    mid = textwrap.indent(pdump(mid), " ")
    if "(" in post or "[" in post or "{" in post:
        post = pdump(post)
    return pre + mid + post


def pprint_ast(s, *, sep=None, end=None, file=None, flush=False, **kwargs):
    """Performs a pretty print of the AST nodes."""
    print(pdump(s, **kwargs), sep=sep, end=end, file=file, flush=flush)


#
# Private helpers
#


def _getblockattr(name, lineno, col):
    """calls getattr(name, '__xonsh_block__', False)."""
    return xonsh_call(
        "getattr",
        args=[
            Name(id=name, ctx=Load(), lineno=lineno, col_offset=col),
            const_str(s="__xonsh_block__", lineno=lineno, col_offset=col),
            const_name(value=False, lineno=lineno, col_offset=col),
        ],
        lineno=lineno,
        col=col,
    )
