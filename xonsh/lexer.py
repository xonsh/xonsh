# -*- coding: utf-8 -*-
"""Lexer for xonsh code.

Written using a hybrid of ``tokenize`` and PLY.
"""
from io import BytesIO
from keyword import kwlist

try:
    from ply.lex import LexToken
except ImportError:
    from xonsh.ply.lex import LexToken

from xonsh.lazyasd import LazyObject
from xonsh.platform import PYTHON_VERSION_INFO
from xonsh.tokenize import (OP, IOREDIRECT, STRING, DOLLARNAME, NUMBER,
    SEARCHPATH, NEWLINE, INDENT, DEDENT, NL, COMMENT, ENCODING,
    ENDMARKER, NAME, ERRORTOKEN, tokenize, TokenError)


def _token_map():
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
    if PYTHON_VERSION_INFO >= (3, 5, 0):
        from xonsh.tokenize import ASYNC, AWAIT
        tm[ASYNC] = 'ASYNC'
        tm[AWAIT] = 'AWAIT'
    return tm


token_map = LazyObject(_token_map, globals(), 'token_map')
"""
Mapping from ``tokenize`` tokens (or token types) to PLY token types.  If a
simple one-to-one mapping from ``tokenize`` to PLY exists, the lexer will look
it up here and generate a single PLY token of the given type.  Otherwise, it
will fall back to handling that token using one of the handlers in
``special_handlers``.
"""
del _token_map

def _make_matcher_handler(tok, typ, pymode, ender):
    matcher = (')' if tok.endswith('(') else
               '}' if tok.endswith('{') else
               ']' if tok.endswith('[') else None)

    def _inner_handler(state, token):
        state['pymode'].append((pymode, tok, matcher, token.start))
        state['last'] = token
        yield _new_token(typ, tok, token.start)
    special_handlers[(OP, tok)] = _inner_handler


def handle_name(state, token):
    """
    Function for handling name tokens
    """
    typ = 'NAME'
    state['last'] = token
    if state['pymode'][-1][0]:
        if token.string in kwlist:
            typ = token.string.upper()
        yield _new_token(typ, token.string, token.start)
    else:
        if token.string == 'and':
            yield _new_token('AND', token.string, token.start)
        elif token.string == 'or':
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
    """
    Function for handling ``}``
    """
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


def handle_error_token(state, token):
    """
    Function for handling error tokens
    """
    state['last'] = token
    if not state['pymode'][-1][0]:
        typ = 'NAME'
    else:
        typ = 'ERRORTOKEN'
    yield _new_token(typ, token.string, token.start)


def handle_ignore(state, token):
    """
    Function for handling tokens that should be ignored
    """
    yield from []


def handle_double_amps(state, token):
    yield _new_token('AND', 'and', token.start)


def handle_double_pipe(state, token):
    yield _new_token('OR', 'or', token.start)


def handle_banglbrace(state, token):
    state['inline_suite_level'] += 1
    sl, sc = token.start
    yield _new_token('NEWLINE', '\n', token.start)
    yield _new_token('INDENT', ' ', (sl, sc+1))


def handle_rbracebang(state, token):
    state['inline_suite_level'] -= 1
    if state['inline_suite_level'] < 0:
        e = "}! used outside of inline suite."
        yield _new_token('ERRORTOKEN', e, token.start)
        return
    sl, sc = token.start
    if state['lexer'].last.type != 'DEDENT':
        yield _new_token('NEWLINE', '\n', token.start)
    yield _new_token('DEDENT', '', (sl, sc+1))


def handle_semicolon(state, token):
    if state['inline_suite_level'] > 0:
        yield _new_token('NEWLINE', '\n', token.start)
        return
    yield _new_token('SEMI', ';', token.start)


special_handlers = {
    NL: handle_ignore,
    COMMENT: handle_ignore,
    ENCODING: handle_ignore,
    ENDMARKER: handle_ignore,
    NAME: handle_name,
    ERRORTOKEN: handle_error_token,
    (OP, ';'): handle_semicolon,
    (OP, ')'): handle_rparen,
    (OP, '}'): handle_rbrace,
    (OP, ']'): handle_rbracket,
    (OP, '&&'): handle_double_amps,
    (OP, '||'): handle_double_pipe,
    (OP, '!{'): handle_banglbrace,
    (OP, '}!'): handle_rbracebang,
    (ERRORTOKEN, ' '): handle_error_space,
}
"""
Mapping from ``tokenize`` tokens (or token types) to the proper function for
generating PLY tokens from them.  In addition to yielding PLY tokens, these
functions may manipulate the Lexer's state.
"""

_make_matcher_handler('(', 'LPAREN', True, ')')
_make_matcher_handler('[', 'LBRACKET', True, ']')
_make_matcher_handler('{', 'LBRACE', True, '}')
_make_matcher_handler('$(', 'DOLLAR_LPAREN', False, ')')
_make_matcher_handler('$[', 'DOLLAR_LBRACKET', False, ']')
_make_matcher_handler('${', 'DOLLAR_LBRACE', True, '}')
_make_matcher_handler('!(', 'BANG_LPAREN', False, ')')
_make_matcher_handler('![', 'BANG_LBRACKET', False, ']')
_make_matcher_handler('@(', 'AT_LPAREN', True, ')')
_make_matcher_handler('@$(', 'ATDOLLAR_LPAREN', False, ')')


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


def get_tokens(s, lexer):
    """
    Given a string containing xonsh code, generates a stream of relevant PLY
    tokens using ``handle_token``.
    """
    state = {'indents': [0], 'last': None,
             'pymode': [(True, '', '', (0, 0))],
             'inline_suite_level': 0,
             'stream': tokenize(BytesIO(s.encode('utf-8')).readline),
             'lexer': lexer}
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
        self.token_stream = get_tokens(s, self)

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

    #
    # All the tokens recognized by the lexer
    #
    tokens = tuple(token_map.values()) + (
        'NAME',                  # name tokens
        'WS',                    # whitespace in subprocess mode
        'SEMI',                  # ;
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
    ) + tuple(i.upper() for i in kwlist)
