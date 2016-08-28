import re

from xonsh import ast
from xonsh.ast import xonsh_call
from xonsh.tokenize import SearchPath
from xonsh.lexer import LexToken
from xonsh.lazyasd import LazyObject


RE_SEARCHPATH = LazyObject(lambda: re.compile(SearchPath), globals(),
                           'RE_SEARCHPATH')


def binop(x, op, y, lineno=None, col=None):
    """Creates the AST node for a binary operation."""
    lineno = x.lineno if lineno is None else lineno
    col = x.col_offset if col is None else col
    return ast.BinOp(left=x, op=op, right=y, lineno=lineno, col_offset=col)


def ensure_list_from_str_or_list(x, lineno=None, col=None):
    """Creates the AST node for the following expression::

        [x] if isinstance(x, str) else x

    Somewhat useful.
    """
    return ast.IfExp(test=ast.Call(func=ast.Name(id='isinstance',
                                                 ctx=ast.Load(),
                                                 lineno=lineno,
                                                 col_offset=col),
                                   args=[x, ast.Name(id='str',
                                                     ctx=ast.Load(),
                                                     lineno=lineno,
                                                     col_offset=col)],
                                   keywords=[],
                                   starargs=None,
                                   kwargs=None,
                                   lineno=lineno,
                                   col_offset=col),
                     body=ast.List(elts=[x],
                                   ctx=ast.Load(),
                                   lineno=lineno,
                                   col_offset=col),
                     orelse=x,
                     lineno=lineno,
                     col_offset=col)


def call_split_lines(x, lineno=None, col=None):
    """Creates the AST node for calling the 'splitlines' attribute of an
    object, nominally a string.
    """
    return ast.Call(func=ast.Attribute(value=x,
                                       attr='splitlines',
                                       ctx=ast.Load(),
                                       lineno=lineno,
                                       col_offset=col),
                    args=[],
                    keywords=[],
                    starargs=None,
                    kwargs=None,
                    lineno=lineno,
                    col_offset=col)


def empty_list(lineno=None, col=None):
    """Creates the AST node for an empty list."""
    return ast.List(elts=[], ctx=ast.Load(), lineno=lineno, col_offset=col)


class SubprocParser(object):
    def p_atom_pathsearch(self, p):
        """atom : SEARCHPATH"""
        p[0] = xonsh_pathsearch(p[1], pymode=True, lineno=self.lineno,
                                col=self.col)

    def p_atom_dname(self, p):
        """atom : DOLLAR_NAME"""
        p[0] = self._envvar_by_name(p[1][1:], lineno=self.lineno, col=self.col)

    def p_atom_fistful_of_dollars(self, p):
        """atom : dollar_lbrace_tok test RBRACE
                | bang_lparen_tok subproc RPAREN
                | dollar_lparen_tok subproc RPAREN
                | bang_lbracket_tok subproc RBRACKET
                | dollar_lbracket_tok subproc RBRACKET
        """
        p[0] = self._dollar_rules(p)

    def p_atom_bang_empty_fistful_of_dollars(self, p):
        """atom : bang_lparen_tok subproc bang_tok RPAREN
                | dollar_lparen_tok subproc bang_tok RPAREN
                | bang_lbracket_tok subproc bang_tok RBRACKET
                | dollar_lbracket_tok subproc bang_tok RBRACKET
        """
        p3 = p[3]
        node = ast.Str(s='', lineno=p3.lineno, col_offset=p3.lexpos + 1)
        p[2][-1].elts.append(node)
        p[0] = self._dollar_rules(p)

    def p_atom_bang_fistful_of_dollars(self, p):
        """atom : bang_lparen_tok subproc bang_tok nocloser rparen_tok
                | dollar_lparen_tok subproc bang_tok nocloser rparen_tok
                | bang_lbracket_tok subproc bang_tok nocloser rbracket_tok
                | dollar_lbracket_tok subproc bang_tok nocloser rbracket_tok
        """
        p3, p5 = p[3], p[5]
        beg = (p3.lineno, p3.lexpos + 1)
        end = (p5.lineno, p5.lexpos)
        s = self.source_slice(beg, end).strip()
        node = ast.Str(s=s, lineno=beg[0], col_offset=beg[1])
        p[2][-1].elts.append(node)
        p[0] = self._dollar_rules(p)

    def _dollar_rules(self, p):
        """These handle the special xonsh $ shell atoms by looking up
        in a special __xonsh_env__ dictionary injected in the __builtin__.
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
        elif p1 == '${':
            xenv = self._xenv(lineno=lineno, col=col)
            idx = ast.Index(value=p2)
            p0 = ast.Subscript(value=xenv, slice=idx, ctx=ast.Load(),
                               lineno=lineno, col_offset=col)
        elif p1 == '$(':
            p0 = xonsh_call('__xonsh_subproc_captured_stdout__', p2,
                            lineno=lineno, col=col)
        elif p1 == '!(':
            p0 = xonsh_call('__xonsh_subproc_captured_object__', p2,
                            lineno=lineno, col=col)
        elif p1 == '![':
            p0 = xonsh_call('__xonsh_subproc_captured_hiddenobject__', p2,
                            lineno=lineno, col=col)
        elif p1 == '$[':
            p0 = xonsh_call('__xonsh_subproc_uncaptured__', p2,
                            lineno=lineno, col=col)
        else:
            assert False
        return p0

    def _xenv(self, lineno, col):
        """Creates a new xonsh env reference."""
        return ast.Name(id='__xonsh_env__', ctx=ast.Load(),
                        lineno=lineno, col_offset=col)

    def _envvar_getter_by_name(self, var, lineno=None, col=None):
        xenv = self._xenv(lineno=lineno, col=col)
        func = ast.Attribute(value=xenv, attr='get', ctx=ast.Load(),
                             lineno=lineno, col_offset=col)
        return ast.Call(func=func,
                        args=[ast.Str(s=var, lineno=lineno, col_offset=col),
                              ast.Str(s='', lineno=lineno, col_offset=col)],
                        keywords=[], starargs=None, kwargs=None,
                        lineno=lineno, col_offset=col)

    def _envvar_by_name(self, var, lineno=None, col=None):
        """Looks up a xonsh variable by name."""
        xenv = self._xenv(lineno=lineno, col=col)
        idx = ast.Index(value=ast.Str(s=var, lineno=lineno, col_offset=col))
        return ast.Subscript(value=xenv, slice=idx, ctx=ast.Load(),
                             lineno=lineno, col_offset=col)

    def _subproc_cliargs(self, args, lineno=None, col=None):
        """Creates an expression for subprocess CLI arguments."""
        cliargs = currlist = empty_list(lineno=lineno, col=col)
        for arg in args:
            action = arg._cliarg_action
            if action == 'append':
                if currlist is None:
                    currlist = empty_list(lineno=lineno, col=col)
                    cliargs = binop(cliargs, ast.Add(), currlist,
                                    lineno=lineno, col=col)
                currlist.elts.append(arg)
            elif action == 'extend':
                cliargs = binop(cliargs, ast.Add(), arg,
                                lineno=lineno, col=col)
                currlist = None
            elif action == 'splitlines':
                sl = call_split_lines(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), sl, lineno=lineno, col=col)
                currlist = None
            elif action == 'ensure_list':
                x = ensure_list_from_str_or_list(arg, lineno=lineno, col=col)
                cliargs = binop(cliargs, ast.Add(), x, lineno=lineno, col=col)
                currlist = None
            else:
                raise ValueError("action not understood: " + action)
            del arg._cliarg_action
        return cliargs

    def p_pipe(self, p):
        """pipe : PIPE
                | WS PIPE
                | PIPE WS
                | WS PIPE WS
        """
        p[0] = ast.Str(s='|', lineno=self.lineno, col_offset=self.col)

    def p_subproc_s2(self, p):
        """subproc : subproc_atoms
                   | subproc_atoms WS
        """
        p1 = p[1]
        p[0] = [self._subproc_cliargs(p1, lineno=self.lineno, col=self.col)]

    def p_subproc_amp(self, p):
        """subproc : subproc AMPERSAND"""
        p1 = p[1]
        p[0] = p1 + [ast.Str(s=p[2], lineno=self.lineno, col_offset=self.col)]

    def p_subproc_pipe(self, p):
        """subproc : subproc pipe subproc_atoms
                   | subproc pipe subproc_atoms WS
        """
        p1 = p[1]
        if len(p1) > 1 and hasattr(p1[-2], 's') and p1[-2].s != '|':
            msg = 'additional redirect following non-pipe redirect'
            self._parse_error(msg, self.currloc(lineno=self.lineno,
                              column=self.col))
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

    #
    # Subproc atom rules
    #
    def p_subproc_atom_uncaptured(self, p):
        """subproc_atom : dollar_lbracket_tok subproc RBRACKET"""

        p1 = p[1]
        p0 = xonsh_call('__xonsh_subproc_uncaptured__', args=p[2],
                        lineno=p1.lineno, col=p1.lexpos)
        p0._cliarg_action = 'splitlines'
        p[0] = p0

    def p_subproc_atom_captured_stdout(self, p):
        """subproc_atom : dollar_lparen_tok subproc RPAREN"""
        p1 = p[1]
        p0 = xonsh_call('__xonsh_subproc_captured_stdout__', args=p[2],
                        lineno=p1.lineno, col=p1.lexpos)
        p0._cliarg_action = 'append'
        p[0] = p0

    def p_subproc_atom_pyenv_lookup(self, p):
        """subproc_atom : dollar_lbrace_tok test RBRACE"""
        p1 = p[1]
        lineno, col = p1.lineno, p1.lexpos
        xenv = self._xenv(lineno=lineno, col=col)
        func = ast.Attribute(value=xenv, attr='get', ctx=ast.Load(),
                             lineno=lineno, col_offset=col)
        p0 = ast.Call(func=func, args=[p[2], ast.Str(s='', lineno=lineno,
                                                     col_offset=col)],
                      keywords=[], starargs=None, kwargs=None, lineno=lineno,
                      col_offset=col)
        p0._cliarg_action = 'append'
        p[0] = p0

    def p_subproc_atom_pyeval(self, p):
        """subproc_atom : AT_LPAREN test RPAREN"""
        p0 = xonsh_call('__xonsh_list_of_strs_or_callables__', [p[2]],
                        lineno=self.lineno, col=self.col)
        p0._cliarg_action = 'extend'
        p[0] = p0

    def p_subproc_atom_subproc_inject(self, p):
        """subproc_atom : ATDOLLAR_LPAREN subproc RPAREN"""
        p0 = xonsh_call('__xonsh_subproc_captured_inject__', p[2],
                        lineno=self.lineno, col=self.col)
        p0._cliarg_action = 'extend'
        p[0] = p0

    def p_subproc_atom_redirect(self, p):
        """subproc_atom : GT
                        | LT
                        | RSHIFT
                        | IOREDIRECT
        """
        p0 = ast.Str(s=p[1], lineno=self.lineno, col_offset=self.col)
        p0._cliarg_action = 'append'
        p[0] = p0

    def p_subproc_atom_re(self, p):
        """subproc_atom : SEARCHPATH"""
        p0 = xonsh_pathsearch(p[1], pymode=False, lineno=self.lineno,
                              col=self.col)
        p0._cliarg_action = 'extend'
        p[0] = p0

    def p_subproc_atom_str(self, p):
        """subproc_atom : string_literal"""
        p0 = xonsh_call('__xonsh_expand_path__', args=[p[1]],
                        lineno=self.lineno, col=self.col)
        p0._cliarg_action = 'append'
        p[0] = p0

    def p_subproc_atom_arg(self, p):
        """subproc_atom : subproc_arg"""
        p1 = p[1]
        p0 = ast.Str(s=p[1], lineno=self.lineno, col_offset=self.col)
        if '*' in p1:
            p0 = xonsh_call('__xonsh_glob__', args=[p0],
                            lineno=self.lineno, col=self.col)
            p0._cliarg_action = 'extend'
        else:
            p0 = xonsh_call('__xonsh_expand_path__', args=[p0],
                            lineno=self.lineno, col=self.col)
            p0._cliarg_action = 'append'
        p[0] = p0

    def p_subproc_arg_single(self, p):
        """subproc_arg : subproc_arg_part"""
        p[0] = p[1]

    def p_subproc_arg_many(self, p):
        """subproc_arg : subproc_arg subproc_arg_part"""
        # This glues the string together after parsing
        p[0] = p[1] + p[2]

    def p_subproc_arg_part(self, p):
        """subproc_arg_part : NAME
                            | TILDE
                            | PERIOD
                            | DIVIDE
                            | MINUS
                            | PLUS
                            | COLON
                            | AT
                            | ATDOLLAR
                            | EQUALS
                            | TIMES
                            | POW
                            | MOD
                            | XOR
                            | DOUBLEDIV
                            | ELLIPSIS
                            | NONE
                            | TRUE
                            | FALSE
                            | NUMBER
                            | STRING
                            | COMMA
                            | QUESTION
                            | DOLLAR_NAME
        """
        # Many tokens cannot be part of this list, such as $, ', ", ()
        # Use a string atom instead.
        p[0] = p[1]


def xonsh_pathsearch(pattern, pymode=False, lineno=None, col=None):
    """Creates the AST node for calling the __xonsh_pathsearch__() function.
    The pymode argument indicate if it is called from subproc or python mode"""
    pymode = ast.NameConstant(value=pymode, lineno=lineno, col_offset=col)
    searchfunc, pattern = RE_SEARCHPATH.match(pattern).groups()
    pattern = ast.Str(s=pattern, lineno=lineno,
                      col_offset=col)
    if searchfunc in {'r', ''}:
        func = '__xonsh_regexsearch__'
    elif searchfunc == 'g':
        func = '__xonsh_globsearch__'
    else:
        func = searchfunc[1:]  # remove the '@' character
    func = ast.Name(id=func, ctx=ast.Load(), lineno=lineno,
                    col_offset=col)
    return xonsh_call('__xonsh_pathsearch__', args=[func, pattern, pymode],
                      lineno=lineno, col=col)
