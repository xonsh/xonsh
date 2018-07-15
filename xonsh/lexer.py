# -*- coding: utf-8 -*-
"""Lexer for xonsh code.

Written using a hybrid of ``tokenize`` and PLY.
"""
import io
# 'keyword' interferes with ast.keyword
import keyword as kwmod
try:
    from ply.lex import LexToken
except ImportError:
    from xonsh.ply.ply.lex import LexToken

from xonsh.lazyasd import lazyobject
from xonsh.platform import PYTHON_VERSION_INFO
from xonsh.tokenize import (OP, IOREDIRECT, STRING, DOLLARNAME, NUMBER,
                            SEARCHPATH, NEWLINE, INDENT, DEDENT, NL, COMMENT,
                            ENCODING, ENDMARKER, NAME, ERRORTOKEN, GREATER,
                            LESS, RIGHTSHIFT, tokenize, TokenError)


@lazyobject
def token_map():
    """Mapping from ``tokenize`` tokens (or token types) to PLY token types. If
    a simple one-to-one mapping from ``tokenize`` to PLY exists, the lexer will
    look it up here and generate a single PLY token of the given type.
    Otherwise, it will fall back to handling that token using one of the
    handlers in``special_handlers``.
    """
    tm = {}
    # operators
    _op_map = {
        # punctuation
        ',': 'COMMA', '.': 'PERIOD', ';': 'SEMI', ':': 'COLON',
        '...': 'ELLIPSIS',
        # basic operators
        '+': 'PLUS', '-': 'MINUS', '*': 'TIMES', '@': 'AT', '/': 'DIVIDE',
        '//': 'DOUBLEDIV', '%': 'MOD', '**': 'POW', '|': 'PIPE',
        '~': 'TILDE', '^': 'XOR', '<<': 'LSHIFT', '>>': 'RSHIFT',
        '<': 'LT', '<=': 'LE', '>': 'GT', '>=': 'GE', '==': 'EQ',
        '!=': 'NE', '->': 'RARROW',
        # assignment operators
        '=': 'EQUALS', '+=': 'PLUSEQUAL', '-=': 'MINUSEQUAL',
        '*=': 'TIMESEQUAL', '@=': 'ATEQUAL', '/=': 'DIVEQUAL', '%=': 'MODEQUAL',
        '**=': 'POWEQUAL', '<<=': 'LSHIFTEQUAL', '>>=': 'RSHIFTEQUAL',
        '&=': 'AMPERSANDEQUAL', '^=': 'XOREQUAL', '|=': 'PIPEEQUAL',
        '//=': 'DOUBLEDIVEQUAL',
        # extra xonsh operators
        '?': 'QUESTION', '??': 'DOUBLE_QUESTION', '@$': 'ATDOLLAR',
        '&': 'AMPERSAND',
    }
    for (op, typ) in _op_map.items():
        tm[(OP, op)] = typ
    tm[IOREDIRECT] = 'IOREDIRECT'
    tm[STRING] = 'STRING'
    tm[DOLLARNAME] = 'DOLLAR_NAME'
    tm[NUMBER] = 'NUMBER'
    tm[SEARCHPATH] = 'SEARCHPATH'
    tm[NEWLINE] = 'NEWLINE'
    tm[INDENT] = 'INDENT'
    tm[DEDENT] = 'DEDENT'
    if (3, 5, 0) <= PYTHON_VERSION_INFO < (3, 7, 0):
        from xonsh.tokenize import ASYNC, AWAIT
        tm[ASYNC] = 'ASYNC'
        tm[AWAIT] = 'AWAIT'
    return tm


def handle_name(state, token):
    """Function for handling name tokens"""
    typ = 'NAME'
    if state['pymode'][-1][0]:
        if token.string in kwmod.kwlist:
            typ = token.string.upper()
        state['last'] = token
        yield _new_token(typ, token.string, token.start)
    else:
        prev = state['last']
        state['last'] = token
        has_whitespace = prev.end != token.start
        if token.string == 'and' and has_whitespace:
            yield _new_token('AND', token.string, token.start)
        elif token.string == 'or' and has_whitespace:
            yield _new_token('OR', token.string, token.start)
        else:
            yield _new_token('NAME', token.string, token.start)


def _end_delimiter(state, token):
    py = state['pymode']
    s = token.string
    l, c = token.start
    if len(py) > 1:
        mode, orig, match, pos = py.pop()
        if s != match:
            e = '"{}" at {} ends "{}" at {} (expected "{}")'
            return e.format(s, (l, c), orig, pos, match)
    else:
        return 'Unmatched "{}" at line {}, column {}'.format(s, l, c)


def handle_rparen(state, token):
    """
    Function for handling ``)``
    """
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RPAREN', ')', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_rbrace(state, token):
    """Function for handling ``}``"""
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RBRACE', '}', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_rbracket(state, token):
    """
    Function for handling ``]``
    """
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RBRACKET', ']', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_error_space(state, token):
    """
    Function for handling special whitespace characters in subprocess mode
    """
    if not state['pymode'][-1][0]:
        state['last'] = token
        yield _new_token('WS', token.string, token.start)
    else:
        yield from []


def handle_error_linecont(state, token):
    """Function for handling special line continuations as whitespace
    characters in subprocess mode.
    """
    if state['pymode'][-1][0]:
        return
    prev = state['last']
    if prev.end != token.start:
        return  # previous token is separated by whitespace
    state['last'] = token
    yield _new_token('WS', '\\', token.start)


def handle_error_token(state, token):
    """
    Function for handling error tokens
    """
    state['last'] = token
    if token.string == '!':
        typ = 'BANG'
    elif not state['pymode'][-1][0]:
        typ = 'NAME'
    else:
        typ = 'ERRORTOKEN'
    yield _new_token(typ, token.string, token.start)


def handle_ignore(state, token):
    """Function for handling tokens that should be ignored"""
    yield from []


def handle_double_amps(state, token):
    yield _new_token('AND', 'and', token.start)


def handle_double_pipe(state, token):
    yield _new_token('OR', 'or', token.start)


def handle_redirect(state, token):
    # The parser expects whitespace after a redirection in subproc mode.
    # If whitespace does not exist, we'll issue an empty whitespace
    # token before proceeding.
    state['last'] = token
    typ = token.type
    st = token.string
    key = (typ, st) if (typ, st) in token_map else typ
    yield _new_token(token_map[key], st, token.start)
    if state['pymode'][-1][0]:
        return
    # add a whitespace token after a redirection, if we need to
    next_tok = next(state['stream'])
    if next_tok.start == token.end:
        yield _new_token('WS', '', token.end)
    yield from handle_token(state, next_tok)


def _make_matcher_handler(tok, typ, pymode, ender, handlers):
    matcher = (')' if tok.endswith('(') else
               '}' if tok.endswith('{') else
               ']' if tok.endswith('[') else None)

    def _inner_handler(state, token):
        state['pymode'].append((pymode, tok, matcher, token.start))
        state['last'] = token
        yield _new_token(typ, tok, token.start)
    handlers[(OP, tok)] = _inner_handler


@lazyobject
def special_handlers():
    """Mapping from ``tokenize`` tokens (or token types) to the proper
    function for generating PLY tokens from them.  In addition to
    yielding PLY tokens, these functions may manipulate the Lexer's state.
    """
    sh = {
        NL: handle_ignore,
        COMMENT: handle_ignore,
        ENCODING: handle_ignore,
        ENDMARKER: handle_ignore,
        NAME: handle_name,
        ERRORTOKEN: handle_error_token,
        LESS: handle_redirect,
        GREATER: handle_redirect,
        RIGHTSHIFT: handle_redirect,
        IOREDIRECT: handle_redirect,
        (OP, '<'): handle_redirect,
        (OP, '>'): handle_redirect,
        (OP, '>>'): handle_redirect,
        (OP, ')'): handle_rparen,
        (OP, '}'): handle_rbrace,
        (OP, ']'): handle_rbracket,
        (OP, '&&'): handle_double_amps,
        (OP, '||'): handle_double_pipe,
        (ERRORTOKEN, ' '): handle_error_space,
        (ERRORTOKEN, '\\\n'): handle_error_linecont,
        (ERRORTOKEN, '\\\r\n'): handle_error_linecont,
    }
    _make_matcher_handler('(', 'LPAREN', True, ')', sh)
    _make_matcher_handler('[', 'LBRACKET', True, ']', sh)
    _make_matcher_handler('{', 'LBRACE', True, '}', sh)
    _make_matcher_handler('$(', 'DOLLAR_LPAREN', False, ')', sh)
    _make_matcher_handler('$[', 'DOLLAR_LBRACKET', False, ']', sh)
    _make_matcher_handler('${', 'DOLLAR_LBRACE', True, '}', sh)
    _make_matcher_handler('!(', 'BANG_LPAREN', False, ')', sh)
    _make_matcher_handler('![', 'BANG_LBRACKET', False, ']', sh)
    _make_matcher_handler('@(', 'AT_LPAREN', True, ')', sh)
    _make_matcher_handler('@$(', 'ATDOLLAR_LPAREN', False, ')', sh)
    return sh


def handle_token(state, token):
    """
    General-purpose token handler.  Makes use of ``token_map`` or
    ``special_map`` to yield one or more PLY tokens from the given input.

    Parameters
    ----------

    state :
        The current state of the lexer, including information about whether
        we are in Python mode or subprocess mode, which changes the lexer's
        behavior.  Also includes the stream of tokens yet to be considered.
    token :
        The token (from ``tokenize``) currently under consideration
    """
    typ = token.type
    st = token.string
    pymode = state['pymode'][-1][0]
    if not pymode:
        if state['last'] is not None and state['last'].end != token.start:
            cur = token.start
            old = state['last'].end
            if cur[0] == old[0] and cur[1] > old[1]:
                yield _new_token('WS', token.line[old[1]:cur[1]], old)
    if (typ, st) in special_handlers:
        yield from special_handlers[(typ, st)](state, token)
    elif (typ, st) in token_map:
        state['last'] = token
        yield _new_token(token_map[(typ, st)], st, token.start)
    elif typ in special_handlers:
        yield from special_handlers[typ](state, token)
    elif typ in token_map:
        state['last'] = token
        yield _new_token(token_map[typ], st, token.start)
    else:
        m = "Unexpected token: {0}".format(token)
        yield _new_token("ERRORTOKEN", m, token.start)


def get_tokens(s):
    """
    Given a string containing xonsh code, generates a stream of relevant PLY
    tokens using ``handle_token``.
    """
    state = {'indents': [0], 'last': None,
             'pymode': [(True, '', '', (0, 0))],
             'stream': tokenize(io.BytesIO(s.encode('utf-8')).readline)}
    while True:
        try:
            token = next(state['stream'])
            yield from handle_token(state, token)
        except StopIteration:
            if len(state['pymode']) > 1:
                pm, o, m, p = state['pymode'][-1]
                l, c = p
                e = 'Unmatched "{}" at line {}, column {}'
                yield _new_token('ERRORTOKEN', e.format(o, l, c), (0, 0))
            break
        except TokenError as e:
            # this is recoverable in single-line mode (from the shell)
            # (e.g., EOF while scanning string literal)
            yield _new_token('ERRORTOKEN', e.args[0], (0, 0))
            break
        except IndentationError as e:
            # this is never recoverable
            yield _new_token('ERRORTOKEN', e, (0, 0))
            break


# synthesize a new PLY token
def _new_token(type, value, pos):
    o = LexToken()
    o.type = type
    o.value = value
    o.lineno, o.lexpos = pos
    return o


class Lexer(object):
    """Implements a lexer for the xonsh language."""

    _tokens = None

    def __init__(self):
        """
        Attributes
        ----------
        fname : str
            Filename
        last : token
            The last token seen.
        lineno : int
            The last line number seen.

        """
        self.fname = ''
        self.last = None
        self.beforelast = None

    def build(self, **kwargs):
        """Part of the PLY lexer API."""
        pass

    def reset(self):
        pass

    def input(self, s):
        """Calls the lexer on the string s."""
        self.token_stream = get_tokens(s)

    def token(self):
        """Retrieves the next token."""
        self.beforelast = self.last
        self.last = next(self.token_stream, None)
        return self.last

    def __iter__(self):
        t = self.token()
        while t is not None:
            yield t
            t = self.token()

    def split(self, s):
        """Splits a string into a list of strings which are whitespace-separated
        tokens.
        """
        vals = []
        self.input(s)
        l = c = -1
        ws = 'WS'
        nl = '\n'
        for t in self:
            if t.type == ws:
                continue
            elif l < t.lineno:
                vals.append(t.value)
            elif len(vals) > 0 and c == t.lexpos:
                vals[-1] = vals[-1] + t.value
            else:
                vals.append(t.value)
            nnl = t.value.count(nl)
            if nnl == 0:
                l = t.lineno
                c = t.lexpos + len(t.value)
            else:
                l = t.lineno + nnl
                c = len(t.value.rpartition(nl)[-1])
        return vals

    #
    # All the tokens recognized by the lexer
    #
    @property
    def tokens(self):
        if self._tokens is None:
            t = tuple(token_map.values()) + (
                'NAME',                  # name tokens
                'BANG',                  # ! tokens
                'WS',                    # whitespace in subprocess mode
                'LPAREN', 'RPAREN',      # ( )
                'LBRACKET', 'RBRACKET',  # [ ]
                'LBRACE', 'RBRACE',      # { }
                'AT_LPAREN',             # @(
                'BANG_LPAREN',           # !(
                'BANG_LBRACKET',         # ![
                'DOLLAR_LPAREN',         # $(
                'DOLLAR_LBRACE',         # ${
                'DOLLAR_LBRACKET',       # $[
                'ATDOLLAR_LPAREN',       # @$(
                'ERRORTOKEN',            # whoops!
            ) + tuple(i.upper() for i in kwmod.kwlist)
            self._tokens = t
        return self._tokens
