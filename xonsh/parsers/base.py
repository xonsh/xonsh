"""Implements the base xonsh parser."""

import itertools
import os
import re
import textwrap
import time
import typing as tp
from ast import parse as pyparse
from collections.abc import Iterable, Mapping, Sequence
from threading import Thread

from xonsh.lib.lazyasd import LazyObject
from xonsh.parsers import ast
from xonsh.parsers.ast import has_elts, load_attribute_chain, xonsh_call
from xonsh.parsers.context_check import check_contexts
from xonsh.parsers.fstring_adaptor import FStringAdaptor
from xonsh.parsers.lexer import Lexer, LexToken
from xonsh.parsers.ply import yacc
from xonsh.parsers.tokenize import SearchPath, StringPrefix
from xonsh.platform import PYTHON_VERSION_INFO

RE_SEARCHPATH = LazyObject(lambda: re.compile(SearchPath), globals(), "RE_SEARCHPATH")
RE_STRINGPREFIX = LazyObject(
    lambda: re.compile(StringPrefix), globals(), "RE_STRINGPREFIX"
)


class Location:
    """Location in a file."""

    def __init__(self, fname, lineno, column=None):
        """Takes a filename, line number, and optionally a column number."""
        self.fname = fname
        self.lineno = lineno
        self.column = column

    def __str__(self):
        s = f"{self.fname}:{self.lineno}"
        if self.column is not None:
            s += f":{self.column}"
        return s


class Index(tp.NamedTuple):
    """From PY39 ast.Index returns the value itself."""

    # todo: since ast.Index is going to be removed in future PY releases, it is better to check for Expr
    #  rather than Index
    value: tp.Any


def ensure_has_elts(x, lineno=None, col_offset=None):
    """Ensures that x is an AST node with elements."""
    if not has_elts(x):
        if not isinstance(x, Iterable):
            x = [x]
        lineno = x[0].lineno if lineno is None else lineno
        col_offset = x[0].col_offset if col_offset is None else col_offset
        x = ast.Tuple(elts=x, ctx=ast.Load(), lineno=lineno, col_offset=col_offset)
    return x


def empty_list(lineno=None, col=None):
    """Creates the AST node for an empty list."""
    return ast.List(elts=[], ctx=ast.Load(), lineno=lineno, col_offset=col)


def binop(x, op, y, lineno=None, col=None):
    """Creates the AST node for a binary operation."""
    lineno = x.lineno if lineno is None else lineno
    col = x.col_offset if col is None else col
    return ast.BinOp(left=x, op=op, right=y, lineno=lineno, col_offset=col)


def call_split_lines(x, lineno=None, col=None):
    """Creates the AST node for calling the 'splitlines' attribute of an
    object, nominally a string.
    """
    return ast.Call(
        func=ast.Attribute(
            value=x, attr="splitlines", ctx=ast.Load(), lineno=lineno, col_offset=col
        ),
        args=[],
        keywords=[],
        lineno=lineno,
        col_offset=col,
    )


def ensure_list_from_str_or_list(x, lineno=None, col=None):
    """Creates the AST node for the following expression::

        [x] if isinstance(x, str) else x

    Somewhat useful.
    """
    return ast.IfExp(
        test=ast.Call(
            func=ast.Name(
                id="isinstance", ctx=ast.Load(), lineno=lineno, col_offset=col
            ),
            args=[x, ast.Name(id="str", ctx=ast.Load(), lineno=lineno, col_offset=col)],
            keywords=[],
            lineno=lineno,
            col_offset=col,
        ),
        body=ast.List(elts=[x], ctx=ast.Load(), lineno=lineno, col_offset=col),
        orelse=x,
        lineno=lineno,
        col_offset=col,
    )


def xonsh_help(x, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh__.help() function."""
    return xonsh_call("__xonsh__.help", [x], lineno=lineno, col=col)


def xonsh_superhelp(x, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh__.superhelp() function."""
    return xonsh_call("__xonsh__.superhelp", [x], lineno=lineno, col=col)


def load_ctx(x):
    """Recursively sets ctx to ast.Load()"""
    if not hasattr(x, "ctx"):
        return
    x.ctx = ast.Load()
    if isinstance(x, (ast.Tuple, ast.List)):
        for e in x.elts:
            load_ctx(e)
    elif isinstance(x, ast.Starred):
        load_ctx(x.value)


def store_ctx(x):
    """Recursively sets ctx to ast.Store()"""
    if not hasattr(x, "ctx"):
        return
    x.ctx = ast.Store()
    if isinstance(x, (ast.Tuple, ast.List)):
        for e in x.elts:
            store_ctx(e)
    elif isinstance(x, ast.Starred):
        store_ctx(x.value)


def del_ctx(x):
    """Recursively sets ctx to ast.Del()"""
    if not hasattr(x, "ctx"):
        return
    x.ctx = ast.Del()
    if isinstance(x, (ast.Tuple, ast.List)):
        for e in x.elts:
            del_ctx(e)
    elif isinstance(x, ast.Starred):
        del_ctx(x.value)


def empty_list_if_newline(x):
    return [] if x == "\n" else x


def lopen_loc(x):
    """Extracts the line and column number for a node that may have an opening
    parenthesis, brace, or bracket.
    """
    lineno = x._lopen_lineno if hasattr(x, "_lopen_lineno") else x.lineno
    col = x._lopen_col if hasattr(x, "_lopen_col") else x.col_offset
    return lineno, col


def hasglobstar(x):
    """Returns True if a node has literal '*' for globbing."""
    if ast.is_const_str(x):
        return "*" in x.value
    elif isinstance(x, list):
        for e in x:
            if hasglobstar(e):
                return True
        else:
            return False
    else:
        return False


def raise_parse_error(
    msg: tp.Union[str, tuple[str]],
    loc: tp.Optional[Location] = None,
    code: tp.Optional[str] = None,
    lines: tp.Optional[list[str]] = None,
):
    err_line = None
    if loc is None or code is None or lines is None:
        err_line_pointer = ""
    else:
        col = loc.column + 1
        if loc.lineno == 0:
            loc.lineno = len(lines)
        i = loc.lineno - 1
        if 0 <= i < len(lines):
            err_line = lines[i].rstrip()
            err_line_pointer = "\n{}\n{: >{}}".format(err_line, "^", col)
        else:
            err_line_pointer = ""
    err = SyntaxError(f"{loc}: {msg}{err_line_pointer}")
    err.loc = loc  # type: ignore

    # if loc is available, construct a proper SyntaxError with all fields
    if loc:
        err.msg = str(msg) if msg else ""
        err.filename = loc.fname
        err.lineno = loc.lineno
        err.offset = loc.column
        err.text = err_line

    raise err


class YaccLoader(Thread):
    """Thread to load (but not shave) the yacc parser."""

    def __init__(self, parser, yacc_kwargs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.parser = parser
        self.yacc_kwargs = yacc_kwargs
        self.start()

    def run(self):
        self.parser.parser = yacc.yacc(**self.yacc_kwargs)


class BaseParser:
    """A base class that parses the xonsh language."""

    def __init__(
        self,
        yacc_optimize=True,
        yacc_table="xonsh.parser_table",
        yacc_debug=False,
        outputdir=None,
    ):
        """Parameters
        ----------
        yacc_optimize : bool, optional
            Set to false when unstable and true when parser is stable.
        yacc_table : str, optional
            Parser module used when optimized.
        yacc_debug : debug, optional
            Dumps extra debug info.
        outputdir : str or None, optional
            The directory to place generated tables within. Defaults to the root
            xonsh dir.
        """
        self.lexer = lexer = Lexer()
        self.tokens = lexer.tokens

        self._lines = None
        self._source = None
        self._attach_nocomma_tok_rules()
        self._attach_nocloser_base_rules()
        self._attach_nodedent_base_rules()
        self._attach_nonewline_base_rules()
        self._attach_subproc_arg_part_rules()

        opt_rules = [
            "newlines",
            "arglist",
            "func_call",
            "rarrow_test",
            "typedargslist",
            "equals_test",
            "colon_test",
            "tfpdef",
            "comma_tfpdef_list",
            "comma_pow_tfpdef",
            "vfpdef",
            "comma_vfpdef_list",
            "comma_pow_vfpdef",
            "equals_yield_expr_or_testlist_list",
            "testlist",
            "as_name",
            "period_or_ellipsis_list",
            "comma_import_as_name_list",
            "comma_dotted_as_name_list",
            "comma_name_list",
            "comma_test",
            "elif_part_list",
            "finally_part",
            "varargslist",
            "or_and_test_list",
            "and_not_test_list",
            "comp_op_expr_list",
            "xor_and_expr_list",
            "ampersand_shift_expr_list",
            "shift_arith_expr_list",
            "op_factor_list",
            "trailer_list",
            "testlist_comp",
            "yield_expr_or_testlist_comp",
            "dictorsetmaker",
            "comma_subscript_list",
            "test",
            "sliceop",
            "comp_iter",
            "yield_arg",
            "test_comma_list",
            "macroarglist",
            "any_raw_toks",
        ]
        for rule in opt_rules:
            self._opt_rule(rule)

        list_rules = [
            "comma_tfpdef",
            "comma_vfpdef",
            "semi_small_stmt",
            "comma_test_or_star_expr",
            "period_or_ellipsis",
            "comma_import_as_name",
            "comma_dotted_as_name",
            "period_name",
            "comma_name",
            "elif_part",
            "except_part",
            "comma_with_item",
            "or_and_test",
            "and_not_test",
            "comp_op_expr",
            "pipe_xor_expr",
            "xor_and_expr",
            "ampersand_shift_expr",
            "shift_arith_expr",
            "pm_term",
            "op_factor",
            "trailer",
            "comma_subscript",
            "comma_expr_or_star_expr",
            "comma_test",
            "comma_argument",
            "comma_item",
            "attr_period_name",
            "test_comma",
            "equals_yield_expr_or_testlist",
            "comma_nocomma",
        ]
        for rule in list_rules:
            self._list_rule(rule)

        tok_rules = [
            "def",
            "class",
            "return",
            "number",
            "name",
            "bang",
            "none",
            "true",
            "false",
            "ellipsis",
            "if",
            "del",
            "assert",
            "lparen",
            "lbrace",
            "lbracket",
            "string",
            "times",
            "plus",
            "minus",
            "divide",
            "doublediv",
            "mod",
            "at",
            "lshift",
            "rshift",
            "pipe",
            "xor",
            "ampersand",
            "for",
            "colon",
            "import",
            "except",
            "nonlocal",
            "global",
            "yield",
            "from",
            "raise",
            "with",
            "dollar_lparen",
            "dollar_lbrace",
            "dollar_lbracket",
            "try",
            "bang_lparen",
            "bang_lbracket",
            "comma",
            "rparen",
            "rbracket",
            "at_lparen",
            "atdollar_lparen",
            "indent",
            "dedent",
            "newline",
            "lambda",
            "ampersandequal",
            "as",
            "atdollar",
            "atequal",
            "break",
            "continue",
            "divequal",
            "dollar_name",
            "double_question",
            "doubledivequal",
            "elif",
            "else",
            "eq",
            "equals",
            "errortoken",
            "finally",
            "ge",
            "in",
            "is",
            "le",
            "lshiftequal",
            "minusequal",
            "modequal",
            "ne",
            "pass",
            "period",
            "pipeequal",
            "plusequal",
            "pow",
            "powequal",
            "question",
            "rarrow",
            "rshiftequal",
            "semi",
            "tilde",
            "timesequal",
            "while",
            "xorequal",
            "match",
            "case",
        ]
        for rule in tok_rules:
            self._tok_rule(rule)

        yacc_kwargs = dict(
            module=self,
            debug=yacc_debug,
            start="start_symbols",
            optimize=yacc_optimize,
            tabmodule=yacc_table,
        )
        if not yacc_debug:
            yacc_kwargs["errorlog"] = yacc.NullLogger()
        if outputdir is None:
            outputdir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        yacc_kwargs["outputdir"] = outputdir
        if yacc_debug:
            # create parser on main thread
            self.parser = yacc.yacc(**yacc_kwargs)
        else:
            self.parser = None
            YaccLoader(self, yacc_kwargs)

        # Keeps track of the last token given to yacc (the lookahead token)
        self._last_yielded_token = None
        self._error = None

    def reset(self):
        """Resets for clean parsing."""
        self.lexer.reset()
        self._last_yielded_token = None
        self._lines = None
        self._source = None
        self._error = None

    def parse(self, s, filename="<code>", mode="exec", debug_level=0):
        """Returns an abstract syntax tree of xonsh code.

        Parameters
        ----------
        s : str
            The xonsh code.
        filename : str, optional
            Name of the file.
        mode : str, optional
            Execution mode, one of: exec, eval, or single.
        debug_level : str, optional
            Debugging level passed down to yacc.

        Returns
        -------
        tree : AST
        """
        self.reset()
        self._source = s
        self.lexer.fname = filename
        while self.parser is None:
            time.sleep(0.01)  # block until the parser is ready
        tree = self.parser.parse(input=s, lexer=self.lexer, debug=debug_level)
        if self._error is not None:
            self._parse_error(self._error[0], self._error[1])
        if tree is not None:
            check_contexts(tree)
        # hack for getting modes right
        if mode == "single":
            if isinstance(tree, ast.Expression):
                tree = ast.Interactive(body=[self.expr(tree.body)])
            elif isinstance(tree, ast.Module):
                tree = ast.Interactive(body=tree.body)
        return tree

    def _lexer_errfunc(self, msg, line, column):
        self._parse_error(msg, self.currloc(line, column))

    def _yacc_lookahead_token(self):
        """Gets the next-to-last and last token seen by the lexer."""
        return self.lexer.beforelast, self.lexer.last

    def _opt_rule(self, rulename):
        """For a rule name, creates an associated optional rule.
        '_opt' is appended to the rule name.
        """

        def optfunc(self, p):
            p[0] = p[1]

        optfunc.__doc__ = f"{rulename}_opt : empty\n" f"        | {rulename}"
        optfunc.__name__ = "p_" + rulename + "_opt"
        setattr(self.__class__, optfunc.__name__, optfunc)

    def _list_rule(self, rulename):
        """For a rule name, creates an associated list rule.
        '_list' is appended to the rule name.
        """

        def listfunc(self, p):
            p[0] = p[1] if len(p) == 2 else p[1] + p[2]

        listfunc.__doc__ = (
            f"{rulename}_list : {rulename}\n" f"         | {rulename}_list {rulename}"
        )
        listfunc.__name__ = "p_" + rulename + "_list"
        setattr(self.__class__, listfunc.__name__, listfunc)

    def _tok_rule(self, rulename):
        """For a rule name, creates a rule that returns the corresponding token.
        '_tok' is appended to the rule name.
        """

        def tokfunc(self, p):
            s, t = self._yacc_lookahead_token()
            uprule = rulename.upper()
            if s is not None and s.type == uprule:
                p[0] = s
            elif t is not None and t.type == uprule:
                p[0] = t
            else:
                raise TypeError(f"token for {rulename!r} not found.")

        tokfunc.__doc__ = f"{rulename}_tok : {rulename.upper()}"
        tokfunc.__name__ = "p_" + rulename + "_tok"
        setattr(self.__class__, tokfunc.__name__, tokfunc)

    def currloc(self, lineno, column=None):
        """Returns the current location."""
        return Location(fname=self.lexer.fname, lineno=lineno, column=column)

    def expr(self, p):
        """Creates an expression for a token."""
        expr = ast.Expr(value=p, lineno=p.lineno, col_offset=p.col_offset)
        expr.max_lineno = self.lineno
        expr.max_col = self.col
        return expr

    def token_col(self, t):
        """Gets ths token column"""
        return t.lexpos

    @property
    def lineno(self):
        if self.lexer.last is None:
            return 1
        else:
            return self.lexer.last.lineno

    @property
    def col(self):
        s, t = self._yacc_lookahead_token()
        if t is not None:
            if t.type == "NEWLINE":
                t = s
            return self.token_col(t)
        return 0

    @property
    def lines(self):
        if self._lines is None and self._source is not None:
            self._lines = self._source.splitlines(keepends=True)
        return self._lines

    def _source_slice(self, start, stop):
        """Gets the original source code from two (line, col) tuples in
        source-space (i.e. lineno start at 1).
        """
        bline, bcol = start
        eline, ecol = stop
        bline -= 1
        lines = self.lines[bline:eline]
        if ecol == 0:
            explen = eline - bline
            if explen == len(lines) and explen > 1:
                lines[-1] = ""
        else:
            lines[-1] = lines[-1][:ecol]
        lines[0] = lines[0][bcol:]
        return "".join(lines)

    def _set_error(self, msg, loc=None):
        assert self._error is None
        if loc is None:
            loc = self.currloc(self.lineno, self.col)
        self._error = (msg, loc)
        raise SyntaxError()

    def _parse_error(self, msg, loc):
        raise_parse_error(msg, loc, self._source, self.lines)

    def xonsh_pathsearch(self, pattern, pymode=False, lineno=None, col=None):
        """Creates the AST node for calling the __xonsh__.pathsearch() function.
        The pymode argument indicate if it is called from subproc or python mode"""
        pymode = ast.const_name(value=pymode, lineno=lineno, col_offset=col)
        searchfunc, pattern = RE_SEARCHPATH.match(pattern).groups()
        if not searchfunc.startswith("@") and "f" in searchfunc:
            pattern_as_str = f"f'''{pattern}'''"
            try:
                pattern = pyparse(pattern_as_str).body[0].value
            except SyntaxError:
                pattern = None
            if pattern is None:
                try:
                    pattern = FStringAdaptor(
                        pattern_as_str, "f", filename=self.lexer.fname
                    ).run()
                except SyntaxError as e:
                    self._set_error(str(e), self.currloc(lineno=lineno, column=col))
        else:
            pattern = ast.const_str(s=pattern, lineno=lineno, col_offset=col)
        pathobj = False
        if searchfunc.startswith("@"):
            func = searchfunc[1:]
        elif "g" in searchfunc:
            func = "__xonsh__.globsearch"
            pathobj = "p" in searchfunc
        else:
            func = "__xonsh__.regexsearch"
            pathobj = "p" in searchfunc
        func = load_attribute_chain(func, lineno=lineno, col=col)
        pathobj = ast.const_name(value=pathobj, lineno=lineno, col_offset=col)
        return xonsh_call(
            "__xonsh__.pathsearch",
            args=[func, pattern, pymode, pathobj],
            lineno=lineno,
            col=col,
        )

    #
    # Precedence of operators
    #
    precedence = (
        ("left", "PIPE"),
        ("left", "XOR"),
        ("left", "AMPERSAND"),
        ("left", "EQ", "NE"),
        ("left", "GT", "GE", "LT", "LE"),
        ("left", "RSHIFT", "LSHIFT"),
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES", "DIVIDE", "DOUBLEDIV", "MOD"),
        ("left", "POW"),
    )

    #
    # Grammar as defined by BNF
    #

    def p_start_symbols(self, p):
        """
        start_symbols : single_input
                      | file_input
                      | eval_input
                      | empty
        """
        p[0] = p[1]

    def p_single_input(self, p):
        """single_input : compound_stmt NEWLINE"""
        p1 = empty_list_if_newline(p[1])
        p0 = ast.Interactive(body=p1)
        p[0] = p0

    def p_file_input(self, p):
        """file_input : file_stmts"""
        if PYTHON_VERSION_INFO < (3, 8, 0):
            p[0] = ast.Module(body=p[1])
        else:
            p[0] = ast.Module(body=p[1], type_ignores=[])

    def p_file_stmts_nl(self, p):
        """file_stmts : newline_or_stmt"""
        # newline_or_stmt ENDMARKER
        p[0] = empty_list_if_newline(p[1])

    def p_file_stmts_files(self, p):
        """file_stmts : file_stmts newline_or_stmt"""
        # file_input newline_or_stmt ENDMARKER
        p2 = empty_list_if_newline(p[2])
        p[0] = p[1] + p2

    def p_newline_or_stmt(self, p):
        """
        newline_or_stmt : NEWLINE
                        | stmt
        """
        p[0] = p[1]

    def p_newlines(self, p):
        """
        newlines : NEWLINE
                 | newlines NEWLINE
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_eval_input(self, p):
        """eval_input : testlist newlines_opt"""
        p1 = p[1]
        p[0] = ast.Expression(body=p1)
        p[0].lineno = p1.lineno
        p[0].col_offset = p1.col_offset

    def p_func_call(self, p):
        """func_call : LPAREN arglist_opt RPAREN"""
        p[0] = p[2]

    def p_attr_period_name(self, p):
        """attr_period_name : PERIOD name_str"""
        p[0] = [p[2]]

    def p_name_str(self, p):
        """
        name_str : name
        """
        p[0] = p[1].value

    def p_name(self, p):
        """
        name : name_tok
             | match_tok
             | case_tok
        """
        p[0] = p[1]

    def p_attr_name(self, p):
        """
        attr_name : attr_name_alone
                  | attr_name_with
        """
        p[0] = p[1]

    def p_attr_name_alone(self, p):
        """attr_name_alone : name"""
        p1 = p[1]
        p[0] = ast.Name(
            id=p1.value, ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.lexpos
        )

    def p_attr_name_with(self, p):
        """attr_name_with : name attr_period_name_list"""
        p1 = p[1]
        name = ast.Name(
            id=p1.value, ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.lexpos
        )
        p2 = p[2]
        p0 = ast.Attribute(
            value=name,
            attr=p2[0],
            ctx=ast.Load(),
            lineno=p1.lineno,
            col_offset=p1.lexpos,
        )
        for a in p2[1:]:
            p0 = ast.Attribute(
                value=p0,
                attr=a,
                ctx=ast.Load(),
                lineno=p0.lineno,
                col_offset=p0.col_offset,
            )
        p[0] = p0

    def p_decorator_no_call(self, p):
        """decorator : at_tok attr_name NEWLINE"""
        p[0] = p[2]

    def p_decorator_call(self, p):
        """decorator : at_tok attr_name func_call NEWLINE"""
        p1, name, p3 = p[1], p[2], p[3]
        if isinstance(name, ast.Attribute) or (p3 is not None):
            lineno, col = name.lineno, name.col_offset
        else:
            lineno, col = p1.lineno, p1.lexpos
        if p3 is None:
            p0 = ast.Call(
                func=name,
                args=[],
                keywords=[],
                lineno=lineno,
                col_offset=col,
            )
        else:
            p0 = ast.Call(func=name, lineno=lineno, col_offset=col, **p3)
        p[0] = p0

    def p_decorators(self, p):
        """
        decorators : decorator
                   | decorators decorator
        """
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    def p_decorated(self, p):
        """decorated : decorators classdef_or_funcdef"""
        p1, p2 = p[1], p[2]
        targ = p2[0]
        targ.decorator_list = p1
        # this is silly, CPython. This claims a func or class starts on
        # the line of the first decorator, rather than the 'def' or 'class'
        # line.  However, it retains the original col_offset.
        targ.lineno = p1[0].lineno
        # async functions take the col number of the 'def', unless they are
        # decorated, in which case they have the col of the 'async'. WAT?
        if hasattr(targ, "_async_tok"):
            targ.col_offset = targ._async_tok.lexpos
            del targ._async_tok
        p[0] = p2

    def p_rarrow_test(self, p):
        """rarrow_test : RARROW test"""
        p[0] = p[2]

    def p_funcdef(self, p):
        """funcdef : def_tok name_str parameters rarrow_test_opt COLON suite"""
        f = ast.FunctionDef(
            name=p[2],
            args=p[3],
            returns=p[4],
            body=p[6],
            decorator_list=[],
            lineno=p[1].lineno,
            col_offset=p[1].lexpos,
        )
        p[0] = [f]

    def p_parameters(self, p):
        """parameters : LPAREN typedargslist_opt RPAREN"""
        p2 = p[2]
        if p2 is None:
            p2 = ast.arguments(
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            )
        p[0] = p2

    def p_equals_test(self, p):
        """equals_test : EQUALS test"""
        p[0] = p[2]

    def p_typedargslist_kwarg(self, p):
        """typedargslist : POW tfpdef"""
        p[0] = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[2], defaults=[]
        )

    def p_typedargslist_times4_tfpdef(self, p):
        """typedargslist : TIMES tfpdef comma_pow_tfpdef_opt"""
        # *args, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[3], defaults=[]
        )
        self._set_var_args(p0, p[2], None)
        p[0] = p0

    def p_typedargslist_times4_comma(self, p):
        """typedargslist : TIMES comma_pow_tfpdef"""
        # *, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[2], defaults=[]
        )
        p[0] = p0

    def p_typedargslist_times5_tdpdef(self, p):
        """typedargslist : TIMES tfpdef comma_tfpdef_list comma_pow_tfpdef_opt"""
        # *args, x, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[4], defaults=[]
        )
        self._set_var_args(p0, p[2], p[3])  # *args
        p[0] = p0

    def p_typedargslist_times5_comma(self, p):
        """typedargslist : TIMES comma_tfpdef_list comma_pow_tfpdef_opt"""
        # *, x, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[3], defaults=[]
        )
        self._set_var_args(p0, None, p[2])  # *args
        p[0] = p0

    def p_typedargslist_t5(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt"""
        # x
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_typedargslist_t7(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt POW tfpdef"""
        # x, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[6], defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_typedargslist_t8(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list_opt"""
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_typedargslist_t10(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt COMMA POW vfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[9], defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], None)
        p[0] = p0

    def p_typedargslist_t11(self, p):
        """typedargslist : tfpdef equals_test_opt comma_tfpdef_list_opt comma_opt TIMES tfpdef_opt comma_tfpdef_list COMMA POW tfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[10],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_colon_test(self, p):
        """colon_test : COLON test"""
        p[0] = p[2]

    def p_tfpdef(self, p):
        """tfpdef : name colon_test_opt"""
        p1 = p[1]
        kwargs = {
            "arg": p1.value,
            "annotation": p[2],
            "lineno": p1.lineno,
            "col_offset": p1.lexpos,
        }
        p[0] = ast.arg(**kwargs)

    def p_comma_tfpdef_empty(self, p):
        """comma_tfpdef : COMMA"""
        p[0] = []

    def p_comma_tfpdef_args(self, p):
        """comma_tfpdef : COMMA tfpdef equals_test_opt"""
        p[0] = [{"arg": p[2], "default": p[3]}]

    def p_comma_pow_tfpdef(self, p):
        """comma_pow_tfpdef : COMMA POW tfpdef"""
        p[0] = p[3]

    def _set_args_def(self, argmts, vals, kwargs=False):
        args, defs = (
            (argmts.kwonlyargs, argmts.kw_defaults)
            if kwargs
            else (argmts.args, argmts.defaults)
        )
        if vals is None and kwargs:
            self._set_error("named arguments must follow bare *")
        for v in vals:
            args.append(v["arg"])
            d = v["default"]
            if kwargs or (d is not None):
                defs.append(d)
            elif defs:
                self._set_error("non-default argument follows default argument")

    def _set_regular_args(self, p0, p1, p2, p3, p4):
        if p2 is None and p3 is None:
            # x
            p0.args.append(p1)
        elif p2 is not None and p3 is None:
            # x=42
            p0.args.append(p1)
            p0.defaults.append(p2)
        elif p2 is None and p3 is not None:
            # x, y and x, y=42
            p0.args.append(p1)
            self._set_args_def(p0, p3)
        else:
            # x=42, y=42
            p0.args.append(p1)
            p0.defaults.append(p2)
            self._set_args_def(p0, p3)

    def _set_var_args(self, p0, vararg, kwargs):
        if vararg is None and kwargs is not None:
            self._set_args_def(p0, kwargs, kwargs=True)
        elif vararg is not None and kwargs is None:
            # *args
            p0.vararg = vararg
        elif vararg is not None and kwargs is not None:
            # *args, x and *args, x, y and *args, x=10 and *args, x=10, y
            # and *args, x, y=10, and *args, x=42, y=65
            p0.vararg = vararg
            self._set_args_def(p0, kwargs, kwargs=True)
        else:
            raise AssertionError()

    def p_varargslist_kwargs(self, p):
        """varargslist : POW vfpdef"""
        p[0] = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[2], defaults=[]
        )

    def p_varargslist_times4(self, p):
        """varargslist : TIMES vfpdef_opt comma_pow_vfpdef_opt"""
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[3], defaults=[]
        )
        self._set_var_args(p0, p[2], None)
        p[0] = p0

    def p_varargslist_times5(self, p):
        """varargslist : TIMES vfpdef_opt comma_vfpdef_list comma_pow_vfpdef_opt"""
        # *args, x, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[4], defaults=[]
        )
        self._set_var_args(p0, p[2], p[3])  # *args
        p[0] = p0

    def p_varargslist_v5(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt"""
        # x
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_varargslist_v7(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt POW vfpdef"""
        # x, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[6], defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        p[0] = p0

    def p_varargslist_v8(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list_opt"""
        # x, *args
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_varargslist_v10(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt COMMA POW vfpdef"""
        # x, *args, **kwargs
        p0 = ast.arguments(
            args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=p[9], defaults=[]
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], None)
        p[0] = p0

    def p_varargslist_v11(self, p):
        """varargslist : vfpdef equals_test_opt comma_vfpdef_list_opt comma_opt TIMES vfpdef_opt comma_vfpdef_list COMMA POW vfpdef"""
        p0 = ast.arguments(
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=p[10],
            defaults=[],
        )
        self._set_regular_args(p0, p[1], p[2], p[3], p[4])
        self._set_var_args(p0, p[6], p[7])
        p[0] = p0

    def p_vfpdef(self, p):
        """vfpdef : name"""
        p1 = p[1]
        kwargs = {
            "arg": p1.value,
            "annotation": None,
            "lineno": p1.lineno,
            "col_offset": p1.lexpos,
        }
        p[0] = ast.arg(**kwargs)

    def p_comma_vfpdef_empty(self, p):
        """comma_vfpdef : COMMA"""
        p[0] = []

    def p_comma_vfpdef_value(self, p):
        """comma_vfpdef : COMMA vfpdef equals_test_opt"""
        p[0] = [{"arg": p[2], "default": p[3]}]

    def p_comma_pow_vfpdef(self, p):
        """comma_pow_vfpdef : COMMA POW vfpdef"""
        p[0] = p[3]

    def p_stmt(self, p):
        """
        stmt : simple_stmt
             | compound_stmt
        """
        p[0] = p[1]

    def p_stmt_list(self, p):
        """
        stmt_list : stmt
                  | stmt_list stmt
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[1] + p[2]

    def p_semi_opt(self, p):
        """
        semi_opt : SEMI
                 | empty
        """
        if len(p) == 2:
            p[0] = p[1]

    def p_semi_small_stmt(self, p):
        """semi_small_stmt : SEMI small_stmt"""
        p[0] = [p[2]]

    def p_simple_stmt_single(self, p):
        """simple_stmt : small_stmt semi_opt NEWLINE"""
        p[0] = [p[1]]

    def p_simple_stmt_many(self, p):
        """simple_stmt : small_stmt semi_small_stmt_list semi_opt NEWLINE"""
        p[0] = [p[1]] + p[2]

    def p_small_stmt(self, p):
        """
        small_stmt : expr_stmt
                   | del_stmt
                   | pass_stmt
                   | flow_stmt
                   | import_stmt
                   | global_stmt
                   | nonlocal_stmt
                   | assert_stmt
        """
        p[0] = p[1]

    _augassign_op = {
        "+=": ast.Add,
        "-=": ast.Sub,
        "*=": ast.Mult,
        "@=": ast.MatMult,
        "/=": ast.Div,
        "%=": ast.Mod,
        "//=": ast.FloorDiv,
        "**=": ast.Pow,
        "^=": ast.BitXor,
        "&=": ast.BitAnd,
        "|=": ast.BitOr,
        "<<=": ast.LShift,
        ">>=": ast.RShift,
    }

    def p_expr_stmt_testlist_assign(self, p):
        """
        expr_stmt : testlist_star_expr equals_yield_expr_or_testlist_list_opt
                  | testlist equals_yield_expr_or_testlist_list_opt
        """
        p1, p2 = p[1], p[2]
        if isinstance(p1, ast.Tuple):
            p1 = [p1]
        if p2 is None and len(p1) == 1:
            p[0] = self.expr(p1[0])
        elif p2 is None:
            raise AssertionError()
        else:
            for targ in p1:
                store_ctx(targ)
            list(map(store_ctx, p2[:-1]))
            lineno, col = lopen_loc(p1[0])
            p[0] = ast.Assign(
                targets=p1 + p2[:-1], value=p2[-1], lineno=lineno, col_offset=col
            )

    def p_expr_stmt_augassign(self, p):
        """expr_stmt : testlist_star_expr augassign yield_expr_or_testlist"""
        p1, p2 = p[1], p[2]
        if not isinstance(p1, ast.Tuple):
            p1 = p1[0]
        store_ctx(p1)
        op = self._augassign_op[p2]
        if op is None:
            self._set_error(
                f"operation {p2!r} not supported",
                self.currloc(lineno=p.lineno, column=p.lexpos),
            )
        p[0] = ast.AugAssign(
            target=p1, op=op(), value=p[3], lineno=p1.lineno, col_offset=p1.col_offset
        )

    def store_star_expr(self, p1, p2, targs, rhs):
        """Stores complex unpacking statements that target *x variables."""
        p1 = [] if p1 is None else p1
        if isinstance(p1, ast.Tuple):
            p1 = [p1]
        for targ in p1:
            store_ctx(targ)
        store_ctx(p2)
        for targ in targs:
            store_ctx(targ)
        p1.append(p2)
        p1.extend(targs)
        p1 = [
            ast.Tuple(
                elts=p1,
                ctx=ast.Store(),
                lineno=p1[0].lineno,
                col_offset=p1[0].col_offset,
            )
        ]
        p0 = ast.Assign(
            targets=p1, value=rhs, lineno=p1[0].lineno, col_offset=p1[0].col_offset
        )
        return p0

    def p_expr_stmt_star5(self, p):
        """expr_stmt : test_comma_list_opt star_expr comma_test_list equals_yield_expr_or_testlist"""
        targs, rhs = p[3], p[4][0]
        p[0] = self.store_star_expr(p[1], p[2], targs, rhs)

    def p_expr_stmt_star6(self, p):
        """expr_stmt : test_comma_list_opt star_expr comma_opt test_comma_list_opt equals_yield_expr_or_testlist"""
        targs, rhs = (p[4] or []), p[5][0]
        p[0] = self.store_star_expr(p[1], p[2], targs, rhs)

    def p_test_comma(self, p):
        """test_comma : test COMMA"""
        p[0] = [p[1]]

    def p_comma_opt(self, p):
        """
        comma_opt : COMMA
                  | empty
        """
        if len(p) == 2:
            p[0] = p[1]

    def p_test_or_star_expr(self, p):
        """
        test_or_star_expr : test
                          | star_expr
        """
        p[0] = p[1]

    def p_comma_test_or_star_expr(self, p):
        """comma_test_or_star_expr : COMMA test_or_star_expr"""
        p[0] = [p[2]]

    def p_testlist_star_expr(self, p):
        """
        testlist_star_expr : test_or_star_expr comma_test_or_star_expr_list comma_opt
                           | test_or_star_expr comma_opt
        """
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = [p1]
        elif p2 == ",":
            p0 = [
                ast.Tuple(
                    elts=[p1],
                    ctx=ast.Load(),
                    lineno=p1.lineno,
                    col_offset=p1.col_offset,
                )
            ]
        else:
            p0 = [
                ast.Tuple(
                    elts=[p1] + p2,
                    ctx=ast.Load(),
                    lineno=p1.lineno,
                    col_offset=p1.col_offset,
                )
            ]
        p[0] = p0

    def p_augassign(self, p):
        """
        augassign    : PLUSEQUAL
                     | MINUSEQUAL
                     | TIMESEQUAL
                     | ATEQUAL
                     | DIVEQUAL
                     | MODEQUAL
                     | AMPERSANDEQUAL
                     | PIPEEQUAL
                     | XOREQUAL
                     | LSHIFTEQUAL
                     | RSHIFTEQUAL
                     | POWEQUAL
                     | DOUBLEDIVEQUAL
        """
        p[0] = p[1]

    def p_yield_expr_or_testlist(self, p):
        """
        yield_expr_or_testlist : yield_expr
                               | testlist
        """
        p[0] = p[1]

    def p_equals_yield_expr_or_testlist(self, p):
        """equals_yield_expr_or_testlist : EQUALS yield_expr_or_testlist"""
        p[0] = [p[2]]

    #
    # For normal assignments, additional restrictions enforced
    # by the interpreter
    #
    def p_del_stmt(self, p):
        """del_stmt : del_tok exprlist"""
        p1 = p[1]
        p2 = p[2]
        for targ in p2:
            del_ctx(targ)
        p0 = ast.Delete(
            targets=p2, ctx=ast.Del(), lineno=p1.lineno, col_offset=p1.lexpos
        )
        p[0] = p0

    def p_pass_stmt(self, p):
        """pass_stmt : PASS"""
        p[0] = ast.Pass(lineno=self.lineno, col_offset=self.col)

    def p_flow_stmt(self, p):
        """
        flow_stmt    : break_stmt
                     | continue_stmt
                     | return_stmt
                     | raise_stmt
                     | yield_stmt
        """
        p[0] = p[1]

    def p_break_stmt(self, p):
        """break_stmt : BREAK"""
        p[0] = ast.Break(lineno=self.lineno, col_offset=self.col)

    def p_continue_stmt(self, p):
        """continue_stmt : CONTINUE"""
        p[0] = ast.Continue(lineno=self.lineno, col_offset=self.col)

    def p_return_stmt(self, p):
        """return_stmt : return_tok testlist_opt"""
        p1 = p[1]
        p[0] = ast.Return(value=p[2], lineno=p1.lineno, col_offset=p1.lexpos)

    def p_yield_stmt(self, p):
        """yield_stmt : yield_expr"""
        p[0] = self.expr(p[1])

    def p_raise_stmt_r1(self, p):
        """raise_stmt : raise_tok"""
        p1 = p[1]
        p[0] = ast.Raise(exc=None, cause=None, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_raise_stmt_r2(self, p):
        """raise_stmt : raise_tok test"""
        p1 = p[1]
        p[0] = ast.Raise(exc=p[2], cause=None, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_raise_stmt_r3(self, p):
        """raise_stmt : raise_tok test FROM test"""
        p1 = p[1]
        p[0] = ast.Raise(exc=p[2], cause=p[4], lineno=p1.lineno, col_offset=p1.lexpos)

    def p_import_stmt(self, p):
        """
        import_stmt    : import_name
                       | import_from
        """
        p[0] = p[1]

    def p_import_name(self, p):
        """import_name : import_tok dotted_as_names"""
        p1 = p[1]
        p[0] = ast.Import(names=p[2], lineno=p1.lineno, col_offset=p1.lexpos)

    def p_import_from_pre_f3(self, p):
        """import_from_pre : from_tok period_or_ellipsis_list"""
        p1 = p[1]
        p[0] = (p[2], p1.lineno, p1.lexpos)

    def p_import_from_pre_f4(self, p):
        """import_from_pre : from_tok period_or_ellipsis_list_opt dotted_name"""
        p1, p2, p3 = p[1], p[2], p[3]
        p0 = p3 if p2 is None else p2 + p3
        p[0] = (p0, p1.lineno, p1.lexpos)

    def p_import_from_post_times(self, p):
        """import_from_post : TIMES"""
        p[0] = [ast.alias(name="*", asname=None)]

    def p_import_from_post_as(self, p):
        """import_from_post : import_as_names"""
        p[0] = p[1]

    def p_import_from_post_paren(self, p):
        """import_from_post : LPAREN import_as_names"""
        p[0] = p[2]

    def p_import_from(self, p):
        """import_from : import_from_pre IMPORT import_from_post"""
        # note below: the ('.' | '...') is necessary because '...' is
        # tokenized as ELLIPSIS
        p1, lineno, col = p[1]
        mod = p1.lstrip(".")
        lvl = len(p1) - len(mod)
        mod = mod or None
        p[0] = ast.ImportFrom(
            module=mod, names=p[3], level=lvl, lineno=lineno, col_offset=col
        )

    def p_period_or_ellipsis(self, p):
        """
        period_or_ellipsis : PERIOD
                           | ELLIPSIS
        """
        p[0] = p[1]

    def p_as_name(self, p):
        """as_name : AS name_str"""
        p[0] = p[2]

    def p_import_as_name(self, p):
        """import_as_name : name_str as_name_opt"""
        p[0] = ast.alias(name=p[1], asname=p[2])

    def p_comma_import_as_name(self, p):
        """comma_import_as_name : COMMA import_as_name"""
        p[0] = [p[2]]

    def p_comma_import_as_name_tail(self, p):
        """comma_import_as_name : comma_opt RPAREN"""
        p[0] = list()

    def p_dotted_as_name(self, p):
        """dotted_as_name : dotted_name as_name_opt"""
        p0 = ast.alias(name=p[1], asname=p[2])
        p[0] = p0

    def p_comma_dotted_as_name(self, p):
        """comma_dotted_as_name : COMMA dotted_as_name"""
        p[0] = [p[2]]

    def p_import_as_names(self, p):
        """import_as_names : import_as_name comma_import_as_name_list_opt"""
        p1, p2 = p[1], p[2]
        p0 = [p1]
        if p2 is not None:
            p0.extend(p2)
        p[0] = p0

    def p_dotted_as_names(self, p):
        """dotted_as_names : dotted_as_name comma_dotted_as_name_list_opt"""
        p1, p2 = p[1], p[2]
        p0 = [p1]
        if p2 is not None:
            p0.extend(p2)
        p[0] = p0

    def p_period_name(self, p):
        """period_name : PERIOD name_str"""
        p[0] = p[1] + p[2]

    def p_dotted_name(self, p):
        """
        dotted_name : name_str
                    | name_str period_name_list
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_comma_name(self, p):
        """comma_name : COMMA name_str"""
        p[0] = [p[2]]

    def p_global_stmt(self, p):
        """global_stmt : global_tok name_str comma_name_list_opt"""
        p1, p2, p3 = p[1], p[2], p[3]
        names = [p2]
        if p3 is not None:
            names += p3
        p[0] = ast.Global(names=names, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_nonlocal_stmt(self, p):
        """nonlocal_stmt : nonlocal_tok name_str comma_name_list_opt"""
        p1, p2, p3 = p[1], p[2], p[3]
        names = [p2]
        if p3 is not None:
            names += p3
        p[0] = ast.Nonlocal(names=names, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_comma_test(self, p):
        """comma_test : COMMA test"""
        p[0] = [p[2]]

    def p_assert_stmt(self, p):
        """assert_stmt : assert_tok test comma_test_opt"""
        p1, p2, p3 = p[1], p[2], p[3]
        if p3 is not None:
            if len(p3) != 1:
                raise AssertionError()
            p3 = p3[0]
        p[0] = ast.Assert(test=p2, msg=p3, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_compound_stmt(self, p):
        """
        compound_stmt : if_stmt
                      | while_stmt
                      | for_stmt
                      | try_stmt
                      | with_stmt
                      | funcdef
                      | classdef
                      | decorated
        """
        p[0] = p[1]

    def p_elif_part(self, p):
        """elif_part : ELIF test COLON suite"""
        p2 = p[2]
        p[0] = [
            ast.If(
                test=p2,
                body=p[4],
                orelse=[],
                lineno=p2.lineno,
                col_offset=p2.col_offset,
            )
        ]

    def p_else_part(self, p):
        """else_part : ELSE COLON suite"""
        p[0] = p[3]

    def p_if_stmt(self, p):
        """
        if_stmt : if_tok test COLON suite elif_part_list_opt
                | if_tok test COLON suite elif_part_list_opt else_part
        """
        p1 = p[1]
        lastif = ast.If(
            test=p[2], body=p[4], orelse=[], lineno=p1.lineno, col_offset=p1.lexpos
        )
        p0 = [lastif]
        p5 = p[5]
        p6 = p[6] if len(p) > 6 else []
        if p5 is not None:
            for elseif in p5:
                lastif.orelse.append(elseif)
                lastif = elseif
        lastif.orelse = p6
        p[0] = p0

    def p_while_stmt(self, p):
        """
        while_stmt : WHILE test COLON suite
                   | WHILE test COLON suite else_part
        """
        p5 = p[5] if len(p) > 5 else []
        p[0] = [
            ast.While(
                test=p[2], body=p[4], orelse=p5, lineno=self.lineno, col_offset=self.col
            )
        ]

    def p_for_stmt(self, p):
        """
        for_stmt : for_tok exprlist IN testlist COLON suite
                 | for_tok exprlist IN testlist COLON suite else_part
        """
        p1, p2 = p[1], p[2]
        p7 = p[7] if len(p) > 7 else []
        if len(p2) == 1:
            p2 = p2[0]
            store_ctx(p2)
        else:
            for x in p2:
                store_ctx(x)
            p2 = ast.Tuple(
                elts=p2,
                ctx=ast.Store(),
                lineno=p2[0].lineno,
                col_offset=p2[0].col_offset,
            )
        p[0] = [
            ast.For(
                target=p2,
                iter=p[4],
                body=p[6],
                orelse=p7,
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_except_part(self, p):
        """except_part : except_clause COLON suite"""
        p0 = p[1]
        p0.body = p[3]
        p[0] = [p0]

    def p_finally_part(self, p):
        """finally_part : FINALLY COLON suite"""
        p[0] = p[3]

    def p_try_stmt_t5(self, p):
        """try_stmt : try_tok COLON suite finally_part"""
        p1 = p[1]
        p[0] = [
            ast.Try(
                body=p[3],
                handlers=[],
                orelse=[],
                finalbody=p[4],
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_try_stmt_t6(self, p):
        """try_stmt : try_tok COLON suite except_part_list finally_part_opt"""
        p1 = p[1]
        p[0] = [
            ast.Try(
                body=p[3],
                handlers=p[4],
                orelse=[],
                finalbody=([] if p[5] is None else p[5]),
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_try_stmt_t7(self, p):
        """try_stmt : try_tok COLON suite except_part_list else_part finally_part_opt"""
        p1 = p[1]
        p[0] = [
            ast.Try(
                body=p[3],
                handlers=p[4],
                orelse=([] if p[5] is None else p[5]),
                finalbody=([] if p[6] is None else p[6]),
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_with_stmt_w5(self, p):
        """with_stmt : with_tok with_item COLON suite"""
        p1 = p[1]
        p[0] = [
            ast.With(items=[p[2]], body=p[4], lineno=p1.lineno, col_offset=p1.lexpos)
        ]

    def p_with_stmt_p6(self, p):
        """with_stmt : with_tok with_item comma_with_item_list COLON suite"""
        p1 = p[1]
        p[0] = [
            ast.With(
                items=[p[2]] + p[3], body=p[5], lineno=p1.lineno, col_offset=p1.lexpos
            )
        ]

    def p_with_bang_stmt_single_suite(self, p):
        """with_stmt : with_tok BANG with_item rawsuite"""
        p1, p3, p4 = p[1], p[3], p[4]
        expr = p3.context_expr
        l, c = expr.lineno, expr.col_offset
        gblcall = xonsh_call("globals", [], lineno=l, col=c)
        loccall = xonsh_call("locals", [], lineno=l, col=c)
        margs = [expr, p4, gblcall, loccall]
        p3.context_expr = xonsh_call("__xonsh__.enter_macro", margs, lineno=l, col=c)
        body = [ast.Pass(lineno=p4.lineno, col_offset=p4.col_offset)]
        p[0] = [ast.With(items=[p3], body=body, lineno=p1.lineno, col_offset=p1.lexpos)]

    def p_with_bang_stmt_many_suite(self, p):
        """with_stmt : with_tok BANG with_item comma_with_item_list rawsuite"""
        p1, p3, p4, p5 = p[1], p[3], p[4], p[5]
        items = [p3] + p4
        for item in items:
            expr = item.context_expr
            l, c = expr.lineno, expr.col_offset
            gblcall = xonsh_call("globals", [], lineno=l, col=c)
            loccall = xonsh_call("locals", [], lineno=l, col=c)
            margs = [expr, p5, gblcall, loccall]
            item.context_expr = xonsh_call(
                "__xonsh__.enter_macro", margs, lineno=l, col=c
            )
        body = [ast.Pass(lineno=p5.lineno, col_offset=p5.col_offset)]
        p[0] = [
            ast.With(items=items, body=body, lineno=p1.lineno, col_offset=p1.lexpos)
        ]

    def p_as_expr(self, p):
        """as_expr : AS expr"""
        p2 = p[2]
        store_ctx(p2)
        p[0] = p2

    def p_with_item(self, p):
        """
        with_item : test
                  | test as_expr
        """
        p2 = p[2] if len(p) > 2 else None
        p[0] = ast.withitem(context_expr=p[1], optional_vars=p2)

    def p_comma_with_item(self, p):
        """comma_with_item : COMMA with_item"""
        p[0] = [p[2]]

    def p_except_clause_e2(self, p):
        """except_clause : except_tok"""
        p1 = p[1]
        p[0] = ast.ExceptHandler(
            type=None, name=None, lineno=p1.lineno, col_offset=p1.lexpos
        )

    def p_except_clause(self, p):
        """except_clause : except_tok test as_name_opt"""
        p1 = p[1]
        p[0] = ast.ExceptHandler(
            type=p[2], name=p[3], lineno=p1.lineno, col_offset=p1.lexpos
        )

    def p_suite(self, p):
        """
        suite : simple_stmt
              | NEWLINE INDENT stmt_list DEDENT
        """
        p[0] = p[1] if len(p) == 2 else p[3]

    def p_rawsuite_indent(self, p):
        """rawsuite : COLON NEWLINE indent_tok nodedent dedent_tok"""
        p3, p5 = p[3], p[5]
        beg = (p3.lineno, p3.lexpos)
        end = (p5.lineno, p5.lexpos)
        s = self._source_slice(beg, end)
        s = textwrap.dedent(s)
        p[0] = ast.const_str(s=s, lineno=beg[0], col_offset=beg[1])

    def p_rawsuite_simple_stmt(self, p):
        """rawsuite : colon_tok nonewline newline_tok"""
        p1, p3 = p[1], p[3]
        beg = (p1.lineno, p1.lexpos + 1)
        end = (p3.lineno, p3.lexpos)
        s = self._source_slice(beg, end).strip()
        p[0] = ast.const_str(s=s, lineno=beg[0], col_offset=beg[1])

    def _attach_nodedent_base_rules(self):
        toks = set(self.tokens)
        toks.remove("DEDENT")
        ts = "\n       | ".join(sorted(toks))
        doc = "nodedent : " + ts + "\n"
        self.p_nodedent_base.__func__.__doc__ = doc

    def p_nodedent_base(self, p):
        # see above attachment function
        pass

    def p_nodedent_any(self, p):
        """nodedent : INDENT any_dedent_toks DEDENT"""
        pass

    def p_nodedent_many(self, p):
        """nodedent : nodedent nodedent"""
        pass

    def p_any_dedent_tok(self, p):
        """
        any_dedent_tok : nodedent
                       | DEDENT
        """
        pass

    def p_any_dedent_toks(self, p):
        """
        any_dedent_toks : any_dedent_tok
                        | any_dedent_toks any_dedent_tok
        """
        pass

    def _attach_nonewline_base_rules(self):
        toks = set(self.tokens)
        toks -= {
            "NEWLINE",
            "LPAREN",
            "RPAREN",
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "AT_LPAREN",
            "BANG_LPAREN",
            "BANG_LBRACKET",
            "DOLLAR_LPAREN",
            "DOLLAR_LBRACE",
            "DOLLAR_LBRACKET",
            "ATDOLLAR_LPAREN",
        }
        ts = "\n        | ".join(sorted(toks))
        doc = "nonewline : " + ts + "\n"
        self.p_nonewline_base.__func__.__doc__ = doc

    def p_nonewline_base(self, p):
        # see above attachment function
        pass

    def p_nonewline_any(self, p):
        """nonewline : any_nested_raw"""
        pass

    def p_nonewline_many(self, p):
        """nonewline : nonewline nonewline"""
        pass

    def p_test_ol(self, p):
        """
        test : or_test
             | lambdef
        """
        p[0] = p[1]

    def p_test_o5(self, p):
        """test : or_test IF or_test ELSE test"""
        p[0] = ast.IfExp(
            test=p[3], body=p[1], orelse=p[5], lineno=self.lineno, col_offset=self.col
        )

    def p_test_nocond(self, p):
        """
        test_nocond : or_test
                    | lambdef_nocond
        """
        p[0] = p[1]

    def p_lambdef(self, p):
        """lambdef : lambda_tok varargslist_opt COLON test"""
        p1, p2, p4 = p[1], p[2], p[4]
        if p2 is None:
            args = ast.arguments(
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            )
        else:
            args = p2
        p0 = ast.Lambda(args=args, body=p4, lineno=p1.lineno, col_offset=p1.lexpos)
        p[0] = p0

    def p_lambdef_nocond(self, p):
        """lambdef_nocond : LAMBDA varargslist_opt COLON test_nocond"""
        raise AssertionError()

    def p_or_test(self, p):
        """or_test : and_test or_and_test_list_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = p1
        elif len(p2) == 2:
            lineno, col = lopen_loc(p1)
            p0 = ast.BoolOp(op=p2[0], values=[p1, p2[1]], lineno=lineno, col_offset=col)
        else:
            lineno, col = lopen_loc(p1)
            p0 = ast.BoolOp(
                op=p2[0], values=[p[1]] + p2[1::2], lineno=lineno, col_offset=col
            )
        p[0] = p0

    def p_or_and_test(self, p):
        """or_and_test : OR and_test"""
        p[0] = [ast.Or(), p[2]]

    def p_and_test(self, p):
        """and_test : not_test and_not_test_list_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = p1
        elif len(p2) == 2:
            lineno, col = lopen_loc(p1)
            p0 = ast.BoolOp(op=p2[0], values=[p1, p2[1]], lineno=lineno, col_offset=col)
        else:
            lineno, col = lopen_loc(p1)
            p0 = ast.BoolOp(
                op=p2[0], values=[p1] + p2[1::2], lineno=lineno, col_offset=col
            )
        p[0] = p0

    def p_and_not_test(self, p):
        """and_not_test : AND not_test"""
        p[0] = [ast.And(), p[2]]

    def p_not_test_not(self, p):
        """not_test : NOT not_test"""
        p[0] = ast.UnaryOp(
            op=ast.Not(), operand=p[2], lineno=self.lineno, col_offset=self.col
        )

    def p_not_test(self, p):
        """not_test : comparison"""
        p[0] = p[1]

    def p_comparison(self, p):
        """comparison : expr comp_op_expr_list_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = p1
        else:
            p0 = ast.Compare(
                left=p1,
                ops=p2[::2],
                comparators=p2[1::2],
                lineno=p1.lineno,
                col_offset=p1.col_offset,
            )
        p[0] = p0

    def p_comp_op_expr(self, p):
        """comp_op_expr : comp_op expr"""
        p[0] = [p[1], p[2]]

    _comp_ops = {
        "<": ast.Lt,
        ">": ast.Gt,
        "==": ast.Eq,
        ">=": ast.GtE,
        "<=": ast.LtE,
        "!=": ast.NotEq,
        "in": ast.In,
        ("not", "in"): ast.NotIn,
        "is": ast.Is,
        ("is", "not"): ast.IsNot,
    }

    def p_comp_op_monograph(self, p):
        """
        comp_op : LT
                | GT
                | EQ
                | GE
                | LE
                | NE
                | IN
                | IS
        """
        p[0] = self._comp_ops[p[1]]()

    def p_comp_op_digraph(self, p):
        """
        comp_op : NOT IN
                | IS NOT
        """
        p[0] = self._comp_ops[(p[1], p[2])]()

    def p_star_expr(self, p):
        """star_expr : times_tok expr"""
        p1 = p[1]
        p[0] = ast.Starred(
            value=p[2], ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.lexpos
        )

    def _binop_combine(self, p1, p2):
        """Combines binary operations"""
        if p2 is None:
            p0 = p1
        elif isinstance(p2, ast.BinOp):
            p2.left = p1
            p0 = p2
        elif isinstance(p2, Sequence) and isinstance(p2[0], ast.BinOp):
            p0 = p2[0]
            p0.left = p1
            p0.lineno, p0.col_offset = lopen_loc(p1)
            for bop in p2[1:]:
                locer = p1 if p0.left is p1 else p0
                bop.left = p0
                p0.lineno, p0.col_offset = lopen_loc(locer)
                p0 = bop
        else:
            p0 = p1 + p2
        return p0

    def p_expr(self, p):
        """
        expr : xor_expr
             | xor_expr pipe_xor_expr_list
        """
        p[0] = self._binop_combine(p[1], p[2] if len(p) > 2 else None)

    def p_pipe_xor_expr(self, p):
        """pipe_xor_expr : pipe_tok xor_expr"""
        p1 = p[1]
        p[0] = [
            ast.BinOp(
                left=None,
                op=ast.BitOr(),
                right=p[2],
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_xor_expr(self, p):
        """xor_expr : and_expr xor_and_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_xor_and_expr(self, p):
        """xor_and_expr : xor_tok and_expr"""
        p1 = p[1]
        p[0] = [
            ast.BinOp(
                left=None,
                op=ast.BitXor(),
                right=p[2],
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_and_expr(self, p):
        """and_expr : shift_expr ampersand_shift_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_ampersand_shift_expr(self, p):
        """ampersand_shift_expr : ampersand_tok shift_expr"""
        p1 = p[1]
        p[0] = [
            ast.BinOp(
                left=None,
                op=ast.BitAnd(),
                right=p[2],
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
        ]

    def p_shift_expr(self, p):
        """shift_expr : arith_expr shift_arith_expr_list_opt"""
        p[0] = self._binop_combine(p[1], p[2])

    def p_shift_arith_expr(self, p):
        """
        shift_arith_expr : lshift_tok arith_expr
                         | rshift_tok arith_expr
        """
        p1 = p[1]
        op = ast.LShift() if p1.value == "<<" else ast.RShift()
        p[0] = [
            ast.BinOp(
                left=None, op=op, right=p[2], lineno=p1.lineno, col_offset=p1.lexpos
            )
        ]

    def p_arith_expr_single(self, p):
        """arith_expr : term"""
        p[0] = p[1]

    def p_arith_expr_many(self, p):
        """arith_expr : term pm_term_list"""
        p1, p2 = p[1], p[2]
        if len(p2) == 2:
            lineno, col = lopen_loc(p1)
            p0 = ast.BinOp(
                left=p1, op=p2[0], right=p2[1], lineno=lineno, col_offset=col
            )
        else:
            left = p1
            for op, right in zip(p2[::2], p2[1::2]):
                locer = left if left is p1 else op
                lineno, col = lopen_loc(locer)
                left = ast.BinOp(
                    left=left, op=op, right=right, lineno=lineno, col_offset=col
                )
            p0 = left
        p[0] = p0

    _term_binops = {
        "+": ast.Add,
        "-": ast.Sub,
        "*": ast.Mult,
        "@": ast.MatMult,
        "/": ast.Div,
        "%": ast.Mod,
        "//": ast.FloorDiv,
    }

    def p_pm_term(self, p):
        """
        pm_term : plus_tok term
                | minus_tok term
        """
        p1 = p[1]
        op = self._term_binops[p1.value]()
        op.lineno, op.col_offset = p1.lineno, p1.lexpos
        p[0] = [op, p[2]]

    def p_term(self, p):
        """term : factor op_factor_list_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = p1
        elif len(p2) == 2:
            lineno, col = lopen_loc(p1)
            p0 = ast.BinOp(
                left=p1, op=p2[0], right=p2[1], lineno=lineno, col_offset=col
            )
        else:
            left = p1
            for op, right in zip(p2[::2], p2[1::2]):
                locer = left if left is p1 else op
                lineno, col = lopen_loc(locer)
                left = ast.BinOp(
                    left=left, op=op, right=right, lineno=lineno, col_offset=col
                )
            p0 = left
        p[0] = p0

    def p_op_factor(self, p):
        """
        op_factor : times_tok factor
                    | at_tok factor
                    | divide_tok factor
                    | mod_tok factor
                    | doublediv_tok factor
        """
        p1 = p[1]
        op = self._term_binops[p1.value]
        if op is None:
            self._set_error(
                f"operation {p1!r} not supported",
                self.currloc(lineno=p.lineno, column=p.lexpos),
            )
        op_node = op()
        op_node.lineno, op_node.col_offset = p1.lineno, p1.lexpos
        p[0] = [op_node, p[2]]

    _factor_ops = {"+": ast.UAdd, "-": ast.USub, "~": ast.Invert}

    def p_factor_power(self, p):
        """factor : power"""
        p[0] = p[1]

    def p_factor_unary(self, p):
        """
        factor : plus_tok factor
               | minus_tok factor
               | tilde_tok factor
        """
        p1 = p[1]
        op = self._factor_ops[p1.value]()
        p[0] = ast.UnaryOp(
            op=op, operand=p[2], lineno=self.lineno, col_offset=p1.lexpos
        )

    def p_power_atom(self, p):
        """power : atom_expr"""
        p[0] = p[1]

    def p_power(self, p):
        """power : atom_expr POW factor"""
        p1 = p[1]
        p[0] = ast.BinOp(
            left=p1,
            op=ast.Pow(),
            right=p[3],
            lineno=p1.lineno,
            col_offset=p1.col_offset,
        )

    def p_yield_expr_or_testlist_comp(self, p):
        """
        yield_expr_or_testlist_comp : yield_expr
                                    | testlist_comp
        """
        p[0] = p[1]

    def _list_or_elts_if_not_real_tuple(self, x):
        if isinstance(x, ast.Tuple) and not (
            hasattr(x, "_real_tuple") and x._real_tuple
        ):
            rtn = x.elts
        else:
            rtn = [x]
        return rtn

    def apply_trailers(self, leader, trailers):
        """Helper function for atom expr."""
        if trailers is None:
            return leader
        p0 = leader
        for trailer in trailers:
            if isinstance(
                trailer,
                (
                    ast.Index,
                    ast.Slice,
                    ast.ExtSlice,
                    ast.Constant,
                    ast.Name,
                    Index,
                ),
            ):
                # unpack types
                slice = trailer.value if isinstance(trailer, Index) else trailer
                p0 = ast.Subscript(
                    value=leader,
                    slice=slice,
                    ctx=ast.Load(),
                    lineno=leader.lineno,
                    col_offset=leader.col_offset,
                )
            elif isinstance(trailer, Mapping):
                # call normal functions
                p0 = ast.Call(
                    func=leader,
                    lineno=leader.lineno,
                    col_offset=leader.col_offset,
                    **trailer,
                )
            elif isinstance(trailer, (ast.Tuple, tuple)):
                # call macro functions
                l, c = leader.lineno, leader.col_offset
                gblcall = xonsh_call("globals", [], lineno=l, col=c)
                loccall = xonsh_call("locals", [], lineno=l, col=c)
                if isinstance(trailer, tuple):
                    trailer, arglist = trailer
                margs = [leader, trailer, gblcall, loccall]
                p0 = xonsh_call("__xonsh__.call_macro", margs, lineno=l, col=c)
            elif isinstance(trailer, str):
                if trailer == "?":
                    p0 = xonsh_help(leader, lineno=leader.lineno, col=leader.col_offset)
                elif trailer == "??":
                    p0 = xonsh_superhelp(
                        leader, lineno=leader.lineno, col=leader.col_offset
                    )
                else:
                    p0 = ast.Attribute(
                        value=leader,
                        attr=trailer,
                        ctx=ast.Load(),
                        lineno=leader.lineno,
                        col_offset=leader.col_offset,
                    )
            else:
                raise AssertionError()
            leader = p0
        return p0

    def p_atom_expr(self, p):
        """atom_expr : atom trailer_list_opt"""
        p[0] = self.apply_trailers(p[1], p[2])

    #
    # Atom rules! (So does Adam!)
    #
    def p_atom_lparen(self, p):
        """atom : lparen_tok yield_expr_or_testlist_comp_opt RPAREN"""
        p1, p2 = p[1], p[2]
        p1, p1_tok = p1.value, p1
        if p2 is None:
            # empty container atom
            p0 = ast.Tuple(
                elts=[], ctx=ast.Load(), lineno=self.lineno, col_offset=self.col
            )
            p0._real_tuple = True
        elif isinstance(p2, ast.AST):
            p0 = p2
            p0._lopen_lineno, p0._lopen_col = p1_tok.lineno, p1_tok.lexpos
            p0._real_tuple = True
        elif len(p2) == 1 and isinstance(p2[0], ast.AST):
            p0 = p2[0]
            p0._lopen_lineno, p0._lopen_col = p1_tok.lineno, p1_tok.lexpos
        else:
            loc = self.currloc(lineno=p.lineno, column=p.lexpos)
            self._set_error(f"code: {p.value}", loc)
        p[0] = p0

    def p_atom_lbraket(self, p):
        """atom : lbracket_tok testlist_comp_opt RBRACKET"""
        p1, p2 = p[1], p[2]
        p1, p1_tok = p1.value, p1
        if p2 is None:
            p0 = ast.List(
                elts=[], ctx=ast.Load(), lineno=self.lineno, col_offset=self.col
            )

        elif isinstance(p2, ast.GeneratorExp):
            p0 = ast.ListComp(
                elt=p2.elt,
                generators=p2.generators,
                lineno=p2.lineno,
                col_offset=p2.col_offset,
            )
        else:
            if isinstance(p2, ast.Tuple):
                if hasattr(p2, "_real_tuple") and p2._real_tuple:
                    elts = [p2]
                else:
                    elts = p2.elts
            else:
                elts = [p2]
            p0 = ast.List(
                elts=elts,
                ctx=ast.Load(),
                lineno=p1_tok.lineno,
                col_offset=p1_tok.lexpos,
            )
        p[0] = p0

    def p_atom_lbrace(self, p):
        """atom : lbrace_tok dictorsetmaker_opt RBRACE"""
        p1, p2 = p[1], p[2]
        p1, p1_tok = p1.value, p1
        if p2 is None:
            p0 = ast.Dict(
                keys=[],
                values=[],
                ctx=ast.Load(),
                lineno=self.lineno,
                col_offset=self.col,
            )
        else:
            p0 = p2
            p0.lineno, p0.col_offset = p1_tok.lineno, p1_tok.lexpos
        p[0] = p0

    def p_atom_ns(self, p):
        """
        atom : number
             | string_literal_list
        """
        p[0] = p[1]

    def p_atom_name(self, p):
        """atom : name"""
        p1 = p[1]
        p[0] = ast.Name(
            id=p1.value, ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.lexpos
        )

    def p_atom_ellip(self, p):
        """atom : ellipsis_tok"""
        p1 = p[1]
        p[0] = ast.Constant(value=..., lineno=p1.lineno, col_offset=p1.lexpos)

    def p_atom_none(self, p):
        """atom : none_tok"""
        p1 = p[1]
        p[0] = ast.const_name(value=None, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_atom_true(self, p):
        """atom : true_tok"""
        p1 = p[1]
        p[0] = ast.const_name(value=True, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_atom_false(self, p):
        """atom : false_tok"""
        p1 = p[1]
        p[0] = ast.const_name(value=False, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_atom_pathsearch(self, p):
        """atom : SEARCHPATH"""
        p[0] = self.xonsh_pathsearch(
            p[1], pymode=True, lineno=self.lineno, col=self.col
        )

    # introduce seemingly superfluous symbol 'atom_dname' to enable reuse it in other places
    def p_atom_dname_indirection(self, p):
        """atom : atom_dname"""
        p[0] = p[1]

    def p_atom_dname(self, p):
        """atom_dname : DOLLAR_NAME"""
        p[0] = self._envvar_by_name(p[1][1:], lineno=self.lineno, col=self.col)

    def p_atom_dollar_rule_atom(self, p):
        """
        atom : dollar_rule_atom
        """
        p[0] = p[1]

    def p_atom_fistful_of_dollars(self, p):
        """
        dollar_rule_atom : dollar_lbrace_tok test RBRACE
                         | bang_lparen_tok subproc RPAREN
                         | dollar_lparen_tok subproc RPAREN
                         | bang_lbracket_tok subproc RBRACKET
                         | dollar_lbracket_tok subproc RBRACKET
        """
        p[0] = self._dollar_rules(p)

    def p_atom_bang_empty_fistful_of_dollars(self, p):
        """
        dollar_rule_atom : bang_lparen_tok subproc bang_tok RPAREN
                         | dollar_lparen_tok subproc bang_tok RPAREN
                         | bang_lbracket_tok subproc bang_tok RBRACKET
                         | dollar_lbracket_tok subproc bang_tok RBRACKET
        """
        self._append_subproc_bang_empty(p)
        p[0] = self._dollar_rules(p)

    def p_atom_bang_fistful_of_dollars(self, p):
        """
        dollar_rule_atom : bang_lparen_tok subproc bang_tok nocloser rparen_tok
                         | dollar_lparen_tok subproc bang_tok nocloser rparen_tok
                         | bang_lbracket_tok subproc bang_tok nocloser rbracket_tok
                         | dollar_lbracket_tok subproc bang_tok nocloser rbracket_tok
        """
        self._append_subproc_bang(p)
        p[0] = self._dollar_rules(p)

    def _attach_nocloser_base_rules(self):
        toks = set(self.tokens)
        toks -= {
            "LPAREN",
            "RPAREN",
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "AT_LPAREN",
            "BANG_LPAREN",
            "BANG_LBRACKET",
            "DOLLAR_LPAREN",
            "DOLLAR_LBRACE",
            "DOLLAR_LBRACKET",
            "ATDOLLAR_LPAREN",
        }
        ts = "\n       | ".join(sorted(toks))
        doc = "nocloser : " + ts + "\n"
        self.p_nocloser_base.__func__.__doc__ = doc

    def p_nocloser_base(self, p):
        # see above attachment function
        pass

    def p_nocloser_any(self, p):
        """nocloser : any_nested_raw"""
        pass

    def p_nocloser_many(self, p):
        """nocloser : nocloser nocloser"""
        pass

    def p_string_literal(self, p):
        """string_literal : string_tok"""
        p1 = p[1]
        prefix = RE_STRINGPREFIX.match(p1.value).group().lower()
        if "p" in prefix and "f" in prefix:
            new_pref = prefix.replace("p", "")
            value_without_p = new_pref + p1.value[len(prefix) :]
            try:
                s = pyparse(value_without_p).body[0].value
            except SyntaxError:
                s = None
            if s is None:
                try:
                    s = FStringAdaptor(
                        value_without_p, new_pref, filename=self.lexer.fname
                    ).run()
                except SyntaxError as e:
                    self._set_error(
                        str(e), self.currloc(lineno=p1.lineno, column=p1.lexpos)
                    )
            s = ast.increment_lineno(s, p1.lineno - 1)
            p[0] = xonsh_call(
                "__xonsh__.path_literal", [s], lineno=p1.lineno, col=p1.lexpos
            )
        elif "p" in prefix:
            value_without_p = prefix.replace("p", "") + p1.value[len(prefix) :]
            s = ast.const_str(
                s=ast.literal_eval(value_without_p),
                lineno=p1.lineno,
                col_offset=p1.lexpos,
            )
            p[0] = xonsh_call(
                "__xonsh__.path_literal", [s], lineno=p1.lineno, col=p1.lexpos
            )
        elif "f" in prefix:
            try:
                s = pyparse(p1.value).body[0].value
            except SyntaxError:
                s = None
            if s is None:
                try:
                    s = FStringAdaptor(
                        p1.value, prefix, filename=self.lexer.fname
                    ).run()
                except SyntaxError as e:
                    self._set_error(
                        str(e), self.currloc(lineno=p1.lineno, column=p1.lexpos)
                    )
            s = ast.increment_lineno(s, p1.lineno - 1)
            if "r" in prefix:
                s.is_raw = True
            p[0] = s
        else:
            s = ast.literal_eval(p1.value)
            is_bytes = "b" in prefix
            is_raw = "r" in prefix
            cls = ast.const_bytes if is_bytes else ast.const_str
            p[0] = cls(s=s, lineno=p1.lineno, col_offset=p1.lexpos, is_raw=is_raw)

    def p_string_literal_list(self, p):
        """
        string_literal_list : string_literal
                            | string_literal_list string_literal
        """
        if len(p) == 3:

            def literal_type(node):
                """
                Determines if a node is a string literal, a bytes literal,
                or a path literal.
                """
                if isinstance(node, ast.Constant):
                    if isinstance(node.value, bytes):
                        return "bytes"
                    else:
                        return "str"  # constant string literal
                elif isinstance(node, ast.Call):
                    return "path"
                else:
                    return "str"  # formatted string literal

            def join_joinedstr_values(x, y):
                """
                Joins two lists that may contain a mix of ast.Constant and
                ast.FormattedValue values (child nodes of ast.JoinedStr).

                If the first list ends with an ast.Constant and the second list
                starts with an ast.Constant, then the two ast.Constants are
                merged into a single value.
                """
                if (
                    len(x) > 0
                    and len(y) > 0
                    and isinstance(x[-1], ast.Constant)
                    and isinstance(y[0], ast.Constant)
                ):
                    # merge the Constant at the head of y
                    # with the Constant at the tail of x
                    x[-1].value += y[0].value
                    x += y[1:]
                else:
                    x += y
                return x

            def join_str_nodes(x, y):
                """
                Joins two str literal nodes into a single node. Each node can
                either be an ast.Constant or an ast.JoinedStr.

                If both nodes are ast.Constants, the resultant node is an
                ast.Constant. Otherwise, the resultant node is an
                ast.JoinedStr.
                """
                if isinstance(x, ast.Constant):
                    if isinstance(y, ast.Constant):
                        x.value += y.value
                        return x
                    else:
                        y.values = join_joinedstr_values([x], y.values)
                        return y
                elif isinstance(y, ast.Constant):
                    x.values = join_joinedstr_values(x.values, [y])
                    return x
                else:
                    x.values = join_joinedstr_values(x.values, y.values)
                    return x

            p1_type = literal_type(p[1])
            p2_type = literal_type(p[2])
            if p1_type == p2_type:
                if p1_type == "path":
                    # the nodes are function calls to __xonsh__.path_literal()
                    # so we need to join their first arguments
                    p[1].args[0] = join_str_nodes(p[1].args[0], p[2].args[0])
                else:
                    p[1] = join_str_nodes(p[1], p[2])
            else:
                self._set_error(
                    "cannot mix literals of different types",
                    self.currloc(lineno=p[1].lineno, column=p[1].col_offset),
                )
        p[0] = p[1]

    def p_number(self, p):
        """number : number_tok"""
        p1 = p[1]
        p[0] = ast.const_num(
            n=ast.literal_eval(p1.value.replace("_", "")),
            lineno=p1.lineno,
            col_offset=p1.lexpos,
        )

    def p_testlist_comp_comp(self, p):
        """testlist_comp : test_or_star_expr comp_for"""
        p1, p2 = p[1], p[2]
        p[0] = ast.GeneratorExp(
            elt=p1, generators=p2["comps"], lineno=p1.lineno, col_offset=p1.col_offset
        )

    def p_testlist_comp_comma(self, p):
        """testlist_comp : test_or_star_expr comma_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:  # split out grouping parentheses.
            p[0] = p1
        else:
            p[0] = ast.Tuple(
                elts=[p1], ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.col_offset
            )

    def p_testlist_comp_many(self, p):
        """testlist_comp : test_or_star_expr comma_test_or_star_expr_list comma_opt"""
        p1, p2 = p[1], p[2]
        p[0] = ast.Tuple(
            elts=[p1] + p2, ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.col_offset
        )

    def p_trailer_lparen(self, p):
        """trailer : LPAREN arglist_opt RPAREN"""
        p[0] = [p[2] or dict(args=[], keywords=[])]

    def p_trailer_bang_lparen(self, p):
        """
        trailer : bang_lparen_tok macroarglist_opt rparen_tok
                | bang_lparen_tok nocomma comma_tok rparen_tok
                | bang_lparen_tok nocomma comma_tok WS rparen_tok
                | bang_lparen_tok macroarglist comma_tok rparen_tok
                | bang_lparen_tok macroarglist comma_tok WS rparen_tok
        """
        p1, p2, p3 = p[1], p[2], p[3]
        begins = [(p1.lineno, p1.lexpos + 2)]
        ends = [(p3.lineno, p3.lexpos)]
        if p2:
            begins.extend([(x[0], x[1] + 1) for x in p2])
            ends = p2 + ends
        elts = []
        for beg, end in zip(begins, ends):
            s = self._source_slice(beg, end).strip()
            if not s:
                if len(begins) == 1:
                    break
                else:
                    msg = "empty macro arguments not allowed"
                    self._set_error(msg, self.currloc(*beg))
            node = ast.const_str(s=s, lineno=beg[0], col_offset=beg[1])
            elts.append(node)
        p0 = ast.Tuple(
            elts=elts, ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.lexpos
        )
        p[0] = [p0]

    def p_trailer_p3(self, p):
        """
        trailer : LBRACKET subscriptlist RBRACKET
                | PERIOD name_str
        """
        p[0] = [p[2]]

    def p_trailer_quest(self, p):
        """
        trailer : DOUBLE_QUESTION
                | QUESTION
        """
        p[0] = [p[1]]

    def _attach_nocomma_tok_rules(self):
        toks = set(self.tokens)
        toks -= {
            "COMMA",
            "LPAREN",
            "RPAREN",
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "AT_LPAREN",
            "BANG_LPAREN",
            "BANG_LBRACKET",
            "DOLLAR_LPAREN",
            "DOLLAR_LBRACE",
            "DOLLAR_LBRACKET",
            "ATDOLLAR_LPAREN",
        }
        ts = "\n            | ".join(sorted(toks))
        doc = "nocomma_tok : " + ts + "\n"
        self.p_nocomma_tok.__func__.__doc__ = doc

    # The following grammar rules are no-ops because we don't need to glue the
    # source code back together piece-by-piece. Instead, we simply look for
    # top-level commas and record their positions. With these positions and the
    # respective positions of the bounding parentheses, we can use the
    # source_slice() method. This does a much better job of capturing exactly
    # the source code that was provided. The tokenizer & lexer can be a little
    # lossy, especially with respect to whitespace.

    def p_nocomma_tok(self, p):
        # see attachment function above for docstring
        pass

    def p_any_raw_tok(self, p):
        """
        any_raw_tok : nocomma
                    | COMMA
        """
        pass

    def p_any_raw_toks_one(self, p):
        """any_raw_toks : any_raw_tok"""
        pass

    def p_any_raw_toks_many(self, p):
        """any_raw_toks : any_raw_toks any_raw_tok"""
        pass

    def p_nocomma_part_tok(self, p):
        """nocomma_part : nocomma_tok"""
        pass

    def p_any_nested_raw(self, p):
        """
        any_nested_raw : LPAREN any_raw_toks_opt RPAREN
                       | LBRACE any_raw_toks_opt RBRACE
                       | LBRACKET any_raw_toks_opt RBRACKET
                       | AT_LPAREN any_raw_toks_opt RPAREN
                       | BANG_LPAREN any_raw_toks_opt RPAREN
                       | BANG_LBRACKET any_raw_toks_opt RBRACKET
                       | DOLLAR_LPAREN any_raw_toks_opt RPAREN
                       | DOLLAR_LBRACE any_raw_toks_opt RBRACE
                       | DOLLAR_LBRACKET any_raw_toks_opt RBRACKET
                       | ATDOLLAR_LPAREN any_raw_toks_opt RPAREN
        """
        pass

    def p_nocomma_part_any(self, p):
        """nocomma_part : any_nested_raw"""
        pass

    def p_nocomma_base(self, p):
        """nocomma : nocomma_part"""
        pass

    def p_nocomma_append(self, p):
        """nocomma : nocomma nocomma_part"""
        pass

    def p_comma_nocomma(self, p):
        """comma_nocomma : comma_tok nocomma"""
        p1 = p[1]
        p[0] = [(p1.lineno, p1.lexpos)]

    def p_macroarglist_single(self, p):
        """macroarglist : nocomma"""
        p[0] = []

    def p_macroarglist_many(self, p):
        """macroarglist : nocomma comma_nocomma_list"""
        p[0] = p[2]

    def p_subscriptlist(self, p):
        """subscriptlist : subscript comma_subscript_list_opt comma_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            pass
        elif isinstance(p1, ast.Slice) or any([isinstance(x, ast.Slice) for x in p2]):
            p1 = ast.ExtSlice(dims=[p1] + p2)
        else:
            p1.value = ast.Tuple(
                elts=[p1.value] + [x.value for x in p2],
                ctx=ast.Load(),
                lineno=p1.lineno,
                col_offset=p1.col_offset,
            )
        p[0] = p1

    def p_comma_subscript(self, p):
        """comma_subscript : COMMA subscript"""
        p[0] = [p[2]]

    def p_subscript_test(self, p):
        """subscript : test"""
        p1 = p[1]
        p[0] = ast.Index(value=p1, lineno=p1.lineno, col_offset=p1.col_offset)

    def p_subscript_tok(self, p):
        """subscript : test_opt colon_tok test_opt sliceop_opt"""
        p1 = p[1]
        if p1 is None:
            p2 = p[2]
            lineno, col = p2.lineno, p2.lexpos
        else:
            lineno, col = p1.lineno, p1.col_offset
        p[0] = ast.Slice(lower=p1, upper=p[3], step=p[4], lineno=lineno, col_offset=col)

    def p_sliceop(self, p):
        """sliceop : COLON test_opt"""
        p[0] = p[2]

    def p_expr_or_star_expr(self, p):
        """
        expr_or_star_expr : expr
                          | star_expr
        """
        p[0] = p[1]

    def p_comma_expr_or_star_expr(self, p):
        """comma_expr_or_star_expr : COMMA expr_or_star_expr"""
        p[0] = [p[2]]

    def p_exprlist_e3(self, p):
        """exprlist : expr_or_star_expr comma_opt"""
        p[0] = [p[1]]

    def p_exprlist_many(self, p):
        """exprlist : expr_or_star_expr comma_expr_or_star_expr_list comma_opt"""
        p2 = p[2]
        p2.insert(0, p[1])
        p[0] = p2

    def p_testlist_test(self, p):
        """testlist : test"""
        p1 = p[1]
        if isinstance(p1, ast.Tuple) and (
            hasattr(p1, "_real_tuple") and p1._real_tuple and p1.elts
        ):
            p1.lineno, p1.col_offset = lopen_loc(p1.elts[0])
        p[0] = p1

    def p_testlist_single(self, p):
        """testlist : test COMMA"""
        p1 = p[1]
        if isinstance(p1, ast.List) or (
            isinstance(p1, ast.Tuple) and hasattr(p1, "_real_tuple") and p1._real_tuple
        ):
            lineno, col = lopen_loc(p1)
            p[0] = ast.Tuple(
                elts=[p1], ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.col_offset
            )
        else:
            p[0] = ensure_has_elts(p[1])

    def p_testlist_many(self, p):
        """
        testlist : test comma_test_list COMMA
                 | test comma_test_list
        """
        p1 = p[1]
        if isinstance(p1, ast.List) or (
            isinstance(p1, ast.Tuple) and hasattr(p1, "_real_tuple") and p1._real_tuple
        ):
            lineno, col = lopen_loc(p1)
            p1 = ast.Tuple(
                elts=[p1], ctx=ast.Load(), lineno=p1.lineno, col_offset=p1.col_offset
            )
        else:
            p1 = ensure_has_elts(p1)
        p1.elts += p[2]
        p[0] = p1

    def p_comma_item(self, p):
        """comma_item : COMMA item"""
        p[0] = p[2]

    #
    # Dict or set maker
    #
    def p_dictorsetmaker_t6(self, p):
        """dictorsetmaker : test COLON test comma_item_list comma_opt"""
        p1, p4 = p[1], p[4]
        keys = [p1]
        vals = [p[3]]
        for k, v in zip(p4[::2], p4[1::2]):
            keys.append(k)
            vals.append(v)
        lineno, col = lopen_loc(p1)
        p[0] = ast.Dict(
            keys=keys, values=vals, ctx=ast.Load(), lineno=lineno, col_offset=col
        )

    def p_dictorsetmaker_i4(self, p):
        """dictorsetmaker : item comma_item_list comma_opt"""
        p1, p2 = p[1], p[2]
        keys = [p1[0]]
        vals = [p1[1]]
        for k, v in zip(p2[::2], p2[1::2]):
            keys.append(k)
            vals.append(v)
        lineno, col = lopen_loc(p1[0] or p1[1])
        p[0] = ast.Dict(
            keys=keys, values=vals, ctx=ast.Load(), lineno=lineno, col_offset=col
        )

    def p_dictorsetmaker_t4_dict(self, p):
        """dictorsetmaker : test COLON testlist"""
        keys = [p[1]]
        vals = self._list_or_elts_if_not_real_tuple(p[3])
        lineno, col = lopen_loc(p[1])
        p[0] = ast.Dict(
            keys=keys, values=vals, ctx=ast.Load(), lineno=lineno, col_offset=col
        )

    def p_dictorsetmaker_item_comma(self, p):
        """dictorsetmaker : item comma_opt"""
        p1 = p[1]
        keys = [p1[0]]
        vals = [p1[1]]
        lineno, col = lopen_loc(p1[0] or p1[1])
        p[0] = ast.Dict(
            keys=keys, values=vals, ctx=ast.Load(), lineno=lineno, col_offset=col
        )

    def p_dictorsetmaker_t4_set(self, p):
        """dictorsetmaker : test_or_star_expr comma_test_or_star_expr_list comma_opt"""
        p[0] = ast.Set(
            elts=[p[1]] + p[2], ctx=ast.Load(), lineno=self.lineno, col_offset=self.col
        )

    def p_dictorsetmaker_test_comma(self, p):
        """dictorsetmaker : test_or_star_expr comma_opt"""
        elts = self._list_or_elts_if_not_real_tuple(p[1])
        p[0] = ast.Set(
            elts=elts, ctx=ast.Load(), lineno=self.lineno, col_offset=self.col
        )

    def p_dictorsetmaker_testlist(self, p):
        """dictorsetmaker : testlist"""
        elts = self._list_or_elts_if_not_real_tuple(p[1])
        p[0] = ast.Set(
            elts=elts, ctx=ast.Load(), lineno=self.lineno, col_offset=self.col
        )

    def p_dictorsetmaker_comp(self, p):
        """
        dictorsetmaker : item comp_for
                       | test_or_star_expr comp_for
        """
        p1 = p[1]
        comps = p[2].get("comps", [])
        if isinstance(p1, list) and len(p1) == 2:
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

    def p_classdef(self, p):
        """classdef : class_tok name_str func_call_opt COLON suite"""
        p1, p3 = p[1], p[3]
        b, kw = ([], []) if p3 is None else (p3["args"], p3["keywords"])
        c = ast.ClassDef(
            name=p[2],
            bases=b,
            keywords=kw,
            body=p[5],
            decorator_list=[],
            lineno=p1.lineno,
            col_offset=p1.lexpos,
        )
        p[0] = [c]

    def p_comma_argument(self, p):
        """comma_argument : COMMA argument"""
        p[0] = [p[2]]

    def p_comp_iter(self, p):
        """
        comp_iter : comp_for
                  | comp_if
        """
        p[0] = p[1]

    def p_comp_for(self, p):
        """comp_for : FOR exprlist IN or_test comp_iter_opt"""
        targs, it, p5 = p[2], p[4], p[5]
        if len(targs) == 1:
            targ = targs[0]
        else:
            targ = ensure_has_elts(targs)
        store_ctx(targ)
        comp = ast.comprehension(target=targ, iter=it, ifs=[], is_async=0)
        comps = [comp]
        p0 = {"comps": comps}
        if p5 is not None:
            comps += p5.get("comps", [])
            comp.ifs += p5.get("if", [])
        p[0] = p0

    def p_comp_if(self, p):
        """comp_if : IF test_nocond comp_iter_opt"""
        p2, p3 = p[2], p[3]
        p0 = {"if": [p2]}
        if p3 is not None:
            p0["comps"] = p3.get("comps", [])
            p0["if"] += p3.get("if", [])
        p[0] = p0

    def p_yield_expr(self, p):
        """yield_expr : yield_tok yield_arg_opt"""
        p1, p2 = p[1], p[2]
        if p2 is None:
            p0 = ast.Yield(value=p2, lineno=p1.lineno, col_offset=p1.lexpos)
        elif p2["from"]:
            p0 = ast.YieldFrom(value=p2["val"], lineno=p1.lineno, col_offset=p1.lexpos)
        else:
            p0 = ast.Yield(value=p2["val"], lineno=p1.lineno, col_offset=p1.lexpos)
        p[0] = p0

    def p_yield_arg_from(self, p):
        """yield_arg : FROM test"""
        p[0] = {"from": True, "val": p[2]}

    def p_yield_arg_testlist(self, p):
        """yield_arg : testlist"""
        p[0] = {"from": False, "val": p[1]}

    #
    # subprocess
    #

    def _get_envvars(self, p, lineno, col):
        """Get replacement environment from subproc_atoms, return None or
        ast.List containing ast.Dict for each subproc_atom in the pipeline.
        """
        if not isinstance(p, list):
            return None
        has_env = False
        envs = empty_list(lineno=lineno, col=col)
        for subproc in p:
            if hasattr(subproc, "_xenvvars"):
                has_env = True
                envs.elts.append(subproc._xenvvars)
            else:
                envs.elts.append(
                    ast.Constant(
                        value=None, lineno=subproc.lineno, col_offset=subproc.col_offset
                    )
                )
        return envs if has_env else None

    def _dollar_rules(self, p):
        """These handle the special xonsh $ shell atoms by looking up
        in a special __xonsh__.env dictionary injected in the __builtin__.
        """
        lenp = len(p)
        p1, p2 = p[1], p[2]
        if isinstance(p1, LexToken):
            p1, p1_tok = p1.value, p1
            lineno, col = p1_tok.lineno, p1_tok.lexpos
        else:
            lineno, col = self.lineno, self.col
        if lenp == 3:  # $NAME
            p0 = self._envvar_by_name(p2, lineno=lineno, col=col)
        elif p1 == "${":
            xenv = load_attribute_chain("__xonsh__.env", lineno=lineno, col=col)
            idx = ast.Index(value=p2)
            p0 = ast.Subscript(
                value=xenv, slice=idx, ctx=ast.Load(), lineno=lineno, col_offset=col
            )
        elif p1 == "$(":
            p0 = xonsh_call(
                "__xonsh__.subproc_captured_stdout", p2, lineno=lineno, col=col
            )
        elif p1 == "!(":
            p0 = xonsh_call(
                "__xonsh__.subproc_captured_object", p2, lineno=lineno, col=col
            )
        elif p1 == "![":
            p0 = xonsh_call(
                "__xonsh__.subproc_captured_hiddenobject", p2, lineno=lineno, col=col
            )
        elif p1 == "$[":
            p0 = xonsh_call("__xonsh__.subproc_uncaptured", p2, lineno=lineno, col=col)
        else:
            raise AssertionError()

        envs = self._get_envvars(p2, lineno, col)
        if envs is not None:
            p0.keywords.append(
                ast.keyword(arg="envs", value=envs, lineno=lineno, col_offset=col)
            )

        return p0

    def _envvar_getter_by_name(self, var, lineno=None, col=None):
        xenv = load_attribute_chain("__xonsh__.env", lineno=lineno, col=col)
        func = ast.Attribute(
            value=xenv, attr="get", ctx=ast.Load(), lineno=lineno, col_offset=col
        )
        return ast.Call(
            func=func,
            args=[
                ast.const_str(s=var, lineno=lineno, col_offset=col),
                ast.const_str(s="", lineno=lineno, col_offset=col),
            ],
            keywords=[],
            lineno=lineno,
            col_offset=col,
        )

    def _envvar_by_name(self, var, lineno=None, col=None):
        """Looks up a xonsh variable by name."""
        xenv = load_attribute_chain("__xonsh__.env", lineno=lineno, col=col)
        idx = ast.Index(value=ast.const_str(s=var, lineno=lineno, col_offset=col))
        return ast.Subscript(
            value=xenv, slice=idx, ctx=ast.Load(), lineno=lineno, col_offset=col
        )

    def _subproc_cliargs(self, args, lineno=None, col=None):
        """Creates an expression for subprocess CLI arguments."""
        cliargs = currlist = empty_list(lineno=lineno, col=col)
        for arg in args:
            action = arg._cliarg_action
            if action == "append":
                if currlist is None:
                    currlist = empty_list(lineno=lineno, col=col)
                    cliargs = binop(
                        cliargs, ast.Add(), currlist, lineno=lineno, col=col
                    )
                currlist.elts.append(arg)
            elif action == "extend":
                cliargs = binop(cliargs, ast.Add(), arg, lineno=lineno, col=col)
                currlist = None
            elif action == "splitlines":
                sl = call_split_lines(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), sl, lineno=lineno, col=col)
                currlist = None
            elif action == "ensure_list":
                x = ensure_list_from_str_or_list(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), x, lineno=lineno, col=col)
                currlist = None
            else:
                raise ValueError("action not understood: " + action)
            del arg._cliarg_action
        if hasattr(args[0], "_xenvvars"):
            cliargs._xenvvars = args[0]._xenvvars
        return cliargs

    def p_pipe(self, p):
        """
        pipe : PIPE
             | WS PIPE
             | PIPE WS
             | WS PIPE WS
        """
        p[0] = ast.const_str(s="|", lineno=self.lineno, col_offset=self.col)

    def p_amper(self, p):
        """
        amper : AMPERSAND
              | WS AMPERSAND
              | AMPERSAND WS
              | WS AMPERSAND WS
        """
        p[0] = ast.const_str(s="&", lineno=self.lineno, col_offset=self.col)

    def p_subproc_s2(self, p):
        """
        subproc : subproc_atoms
                | subproc_atoms WS
        """
        p1 = p[1]
        p[0] = [self._subproc_cliargs(p1, lineno=self.lineno, col=self.col)]

    def p_subproc_s1(self, p):
        """subproc : WS subproc"""
        p[0] = p[2]

    def p_subproc_amper(self, p):
        """subproc : subproc amper"""
        p1 = p[1]
        p[0] = p1 + [p[2]]

    def p_subproc_pipe(self, p):
        """
        subproc : subproc pipe subproc_atoms
                | subproc pipe subproc_atoms WS
        """
        p1 = p[1]
        if len(p1) > 1 and hasattr(p1[-2], "value") and p1[-2].value != "|":
            self._set_error("additional redirect following non-pipe redirect")
        cliargs = self._subproc_cliargs(p[3], lineno=self.lineno, col=self.col)
        p[0] = p1 + [p[2], cliargs]

    def p_subproc_atoms_single(self, p):
        """subproc_atoms : subproc_atom"""
        p[0] = [p[1]]

    def p_subproc_atoms_many(self, p):
        """subproc_atoms : subproc_atoms WS subproc_atom"""
        p1 = p[1]
        p1.append(p[3])
        p[0] = p1

    def p_subproc_atoms_subshell(self, p):
        """
        subproc_atoms : lparen_tok any_raw_tok rparen_tok
                      | lparen_tok any_raw_toks rparen_tok
        """
        p1 = p[1]
        p3 = p[3]
        l = p1.lineno
        c = p1.lexpos + 1
        subcmd = self._source_slice((l, c), (p3.lineno, p3.lexpos))
        subcmd = subcmd.strip() + "\n"
        p0 = [
            ast.const_str(s="xonsh", lineno=l, col_offset=c),
            ast.const_str(s="-c", lineno=l, col_offset=c),
            ast.const_str(s=subcmd, lineno=l, col_offset=c),
        ]
        for arg in p0:
            arg._cliarg_action = "append"
        p[0] = p0

    def p_envvar_assign_subproc_atoms(self, p):
        """
        subproc_atoms : envvar_assign subproc_atoms
                      | envvar_assign subproc_atoms WS
        """
        p1, p20 = p[1], p[2][0]
        if hasattr(p20, "_xenvvars"):
            p20._xenvvars.keys.append(p1.keys[0])
            p20._xenvvars.values.append(p1.values[0])
        else:
            p20._xenvvars = p1
        p[0] = p[2]

    #
    # Subproc atom rules
    #
    def _append_subproc_bang_empty(self, p):
        """Appends an empty string in subprocess mode to the argument list."""
        p3 = p[3]
        node = ast.const_str(s="", lineno=p3.lineno, col_offset=p3.lexpos + 1)
        p[2][-1].elts.append(node)

    def _append_subproc_bang(self, p):
        """Appends the part between ! and the ) or ] in subprocess mode to the
        argument list.
        """
        p3, p5 = p[3], p[5]
        beg = (p3.lineno, p3.lexpos + 1)
        end = (p5.lineno, p5.lexpos)
        s = self._source_slice(beg, end).strip()
        node = ast.const_str(s=s, lineno=beg[0], col_offset=beg[1])
        p[2][-1].elts.append(node)

    def p_subproc_atom_uncaptured(self, p):
        """subproc_atom : dollar_lbracket_tok subproc RBRACKET"""
        p1 = p[1]
        p0 = xonsh_call(
            "__xonsh__.subproc_uncaptured", args=p[2], lineno=p1.lineno, col=p1.lexpos
        )
        p0._cliarg_action = "splitlines"
        p[0] = p0

    def p_subproc_atom_uncaptured_bang_empty(self, p):
        """subproc_atom : dollar_lbracket_tok subproc bang_tok RBRACKET"""
        self._append_subproc_bang_empty(p)
        self.p_subproc_atom_uncaptured(p)

    def p_subproc_atom_uncaptured_bang(self, p):
        """subproc_atom : dollar_lbracket_tok subproc bang_tok nocloser rbracket_tok"""
        self._append_subproc_bang(p)
        self.p_subproc_atom_uncaptured(p)

    def p_subproc_atom_captured_stdout(self, p):
        """subproc_atom : dollar_lparen_tok subproc RPAREN"""
        p1 = p[1]
        p0 = xonsh_call(
            "__xonsh__.subproc_captured_stdout",
            args=p[2],
            lineno=p1.lineno,
            col=p1.lexpos,
        )
        p0._cliarg_action = "append"
        p[0] = p0

    def p_subproc_atom_captured_stdout_bang_empty(self, p):
        """subproc_atom : dollar_lparen_tok subproc bang_tok RPAREN"""
        self._append_subproc_bang_empty(p)
        self.p_subproc_atom_captured_stdout(p)

    def p_subproc_atom_captured_stdout_bang(self, p):
        """subproc_atom : dollar_lparen_tok subproc bang_tok nocloser rparen_tok"""
        self._append_subproc_bang(p)
        self.p_subproc_atom_captured_stdout(p)

    def p_subproc_atom_pyenv_lookup(self, p):
        """subproc_atom : dollar_lbrace_tok test RBRACE"""
        p1 = p[1]
        lineno, col = p1.lineno, p1.lexpos
        xenv = load_attribute_chain("__xonsh__.env", lineno=lineno, col=col)
        func = ast.Attribute(
            value=xenv, attr="get", ctx=ast.Load(), lineno=lineno, col_offset=col
        )
        p0 = ast.Call(
            func=func,
            args=[p[2], ast.const_str(s="", lineno=lineno, col_offset=col)],
            keywords=[],
            lineno=lineno,
            col_offset=col,
        )
        p0._cliarg_action = "append"
        p[0] = p0

    def p_subproc_atom_pyeval(self, p):
        """
        subproc_atom : at_lparen_tok testlist_comp RPAREN
        subproc_arg_part : at_lparen_tok testlist_comp RPAREN
        """
        p1 = p[1]
        p0 = xonsh_call(
            "__xonsh__.list_of_strs_or_callables",
            [p[2]],
            lineno=p1.lineno,
            col=p1.lexpos,
        )
        p0._cliarg_action = "extend"
        p[0] = p0

    def p_subproc_atom_subproc_inject(self, p):
        """
        subproc_atom : atdollar_lparen_tok subproc RPAREN
        subproc_arg_part : atdollar_lparen_tok subproc RPAREN
        """
        p1, p2 = p[1], p[2]
        p0 = xonsh_call(
            "__xonsh__.subproc_captured_inject", p2, lineno=p1.lineno, col=p1.lexpos
        )
        p0._cliarg_action = "extend"
        envs = self._get_envvars(p2, lineno=p2[0].lineno, col=p2[0].col_offset)
        if envs is not None:
            p0.keywords.append(ast.keyword(arg="envs", value=envs))
        p[0] = p0

    def p_subproc_atom_subproc_inject_bang_empty(self, p):
        """
        subproc_atom : atdollar_lparen_tok subproc bang_tok RPAREN
        subproc_arg_part : atdollar_lparen_tok subproc bang_tok RPAREN
        """
        self._append_subproc_bang_empty(p)
        self.p_subproc_atom_subproc_inject(p)

    def p_subproc_atom_subproc_inject_bang(self, p):
        """
        subproc_atom : atdollar_lparen_tok subproc bang_tok nocloser rparen_tok
        subproc_arg_part : atdollar_lparen_tok subproc bang_tok nocloser rparen_tok
        """
        self._append_subproc_bang(p)
        self.p_subproc_atom_subproc_inject(p)

    def p_subproc_atom_redirect(self, p):
        """
        subproc_atom : GT WS subproc_atom
                     | LT WS subproc_atom
                     | RSHIFT WS subproc_atom
                     | IOREDIRECT1 WS subproc_atom
                     | IOREDIRECT2
        """
        operator = ast.const_str(s=p[1], lineno=self.lineno, col_offset=self.col)
        elts = [operator] if len(p) == 2 else [operator, p[3]]
        p0 = ast.Tuple(
            elts=elts,
            ctx=ast.Load(),
            lineno=self.lineno,
            col_offset=self.col,
        )
        p0._cliarg_action = "append"
        p[0] = p0

    def p_subproc_atom_re(self, p):
        """subproc_atom : SEARCHPATH"""
        p0 = self.xonsh_pathsearch(p[1], pymode=False, lineno=self.lineno, col=self.col)
        p0._cliarg_action = "extend"
        p[0] = p0

    def p_subproc_atom_str(self, p):
        """subproc_atom : string_literal"""
        if hasattr(p[1], "is_raw") and p[1].is_raw:
            p0 = p[1]
        else:
            p0 = xonsh_call(
                "__xonsh__.expand_path", args=[p[1]], lineno=self.lineno, col=self.col
            )
        p0._cliarg_action = "append"
        p[0] = p0

    def p_subproc_atom_arg(self, p):
        """subproc_atom : subproc_arg"""
        p1 = p[1]
        if isinstance(p1, list):
            # has an expanding function call, such as @(x)
            p0 = xonsh_call(
                "__xonsh__.list_of_list_of_strs_outer_product",
                args=[ensure_has_elts(p1)],
                lineno=p1[0].lineno,
                col=p1[0].col_offset,
            )
            p0._cliarg_action = "extend"
        elif hasglobstar(p1):
            # globbed literal argument
            p0 = xonsh_call(
                "__xonsh__.glob", args=[p1], lineno=p1.lineno, col=p1.col_offset
            )
            p0._cliarg_action = "extend"
        else:
            # literal str argument
            p0 = xonsh_call(
                "__xonsh__.expand_path", args=[p1], lineno=p1.lineno, col=p1.col_offset
            )
            p0._cliarg_action = "append"
        p[0] = p0

    def p_subproc_arg_single(self, p):
        """subproc_arg : subproc_arg_part"""
        p[0] = p[1]

    def _arg_part_combine(self, *arg_parts):
        """Combines arg_parts. If all arg_parts are strings, concatenate the strings.
        Otherwise, return a list of arg_parts."""
        if all(ast.is_const_str(ap) for ap in arg_parts):
            return ast.const_str(
                "".join(ap.value for ap in arg_parts),
                lineno=arg_parts[0].lineno,
                col_offset=arg_parts[0].col_offset,
            )
        else:
            return list(
                itertools.chain.from_iterable(
                    ap if isinstance(ap, list) else [ap] for ap in arg_parts
                )
            )

    def p_subproc_arg_many(self, p):
        """subproc_arg : subproc_arg subproc_arg_part"""
        # This glues the string together after parsing
        p[0] = self._arg_part_combine(p[1], p[2])

    def p_subproc_arg_part_brackets(self, p):
        """subproc_arg_part : lbracket_tok subproc_arg rbracket_tok"""
        p1 = p[1]
        p2 = p[2]
        p3 = p[3]
        p1 = ast.const_str(s=p1.value, lineno=p1.lineno, col_offset=p1.lexpos)
        p3 = ast.const_str(s=p3.value, lineno=p3.lineno, col_offset=p3.lexpos)
        p[0] = self._arg_part_combine(p1, p2, p3)

    def p_subproc_arg_part_brackets_empty(self, p):
        """subproc_arg_part : lbracket_tok rbracket_tok"""
        p1 = p[1]
        p2 = p[2]
        p1 = ast.const_str(s=p1.value, lineno=p1.lineno, col_offset=p1.lexpos)
        p2 = ast.const_str(s=p2.value, lineno=p2.lineno, col_offset=p2.lexpos)
        p[0] = self._arg_part_combine(p1, p2)

    def _attach_subproc_arg_part_rules(self):
        toks = set(self.tokens)
        toks -= {
            "AND",
            "OR",
            "NOT",
            "BANG",
            "PIPE",
            "WS",
            "GT",
            "LT",
            "LSHIFT",
            "RSHIFT",
            "IOREDIRECT1",
            "IOREDIRECT2",
            "SEARCHPATH",
            "INDENT",
            "DEDENT",
            "LPAREN",
            "RPAREN",
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "AT_LPAREN",
            "BANG_LPAREN",
            "BANG_LBRACKET",
            "DOLLAR_LPAREN",
            "DOLLAR_LBRACE",
            "DOLLAR_LBRACKET",
            "ATDOLLAR_LPAREN",
            "AMPERSAND",
        }
        ts = "\n                 | ".join(sorted(t.lower() + "_tok" for t in toks))
        doc = "subproc_arg_part : " + ts + "\n"
        self.p_subproc_arg_part.__func__.__doc__ = doc

    def p_subproc_arg_part(self, p):
        # Many tokens cannot be part of this rule, such as $, ', ", ()
        # Use a string atom instead. See above attachment functions
        p1 = p[1]
        p[0] = ast.const_str(s=p1.value, lineno=p1.lineno, col_offset=p1.lexpos)

    def p_envvar_assign_left(self, p):
        """envvar_assign_left : dollar_name_tok EQUALS"""
        p[0] = p[1]

    def p_envvar_assign(self, p):
        """
        envvar_assign : envvar_assign_left test WS
                      | envvar_assign_left subproc_atom WS
        """
        p1, p2 = p[1], p[2]
        p[0] = ast.Dict(
            keys=[
                ast.Constant(value=p1.value[1:], lineno=p1.lineno, col_offset=p1.lexpos)
            ],
            values=[p2],
            lineno=p1.lineno,
            col_offset=p1.lexpos,
        )

    #
    # Helpers
    #

    def p_test_comma_combine(self, p):
        """
        test_comma_list : test comma_test_list
                        | test comma_test_list COMMA
        """
        p2 = p[2]
        p2.insert(0, p[1])
        p[0] = p2

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    def p_error(self, p):
        if p is None:
            self._parse_error("no further code", None)
        elif p.type == "ERRORTOKEN":
            if isinstance(p.value, BaseException):
                raise p.value
            else:
                self._parse_error(
                    p.value, self.currloc(lineno=p.lineno, column=p.lexpos)
                )
        else:
            msg = (f"code: {p.value}",)
            self._parse_error(msg, self.currloc(lineno=p.lineno, column=p.lexpos))
