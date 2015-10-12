"""
Lexer for xonsh code, written using a hybrid of ``tokenize`` and PLY
"""
import re
import sys
import tokenize

from io import BytesIO
from keyword import kwlist

from ply import lex
from ply.lex import TOKEN, LexToken

from xonsh.tools import VER_3_5, VER_MAJOR_MINOR

future_kwlist = []

token_map = {}
"""
Mapping from ``tokenize`` tokens (or token types) to PLY token types.  If a
simple one-to-one mapping from ``tokenize`` to PLY exists, the lexer will look
it up here and generate a single PLY token of the given type.  Otherwise, it
will fall back to handling that token using one of the handlers in
``special_handlers``.
"""

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
}
for (op, type) in _op_map.items():
    token_map[(tokenize.OP, op)] = type

token_map[tokenize.STRING] = 'STRING'
token_map[tokenize.NEWLINE] = 'NEWLINE'
token_map[tokenize.INDENT] = 'INDENT'
token_map[tokenize.DEDENT] = 'DEDENT'
if VER_3_5 <= VER_MAJOR_MINOR:
    token_map[tokenize.ASYNC] = 'ASYNC'
    token_map[tokenize.AWAIT] = 'AWAIT'
else:
    future_kwlist += ['async', 'await']

_REDIRECT_NAMES = frozenset({'out', 'err', 'all', 'o', 'e', 'a'})


def handle_name(state, token, stream):
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
        # subprocess mode
        n = next(stream, None)
        string = token.string
        if (n is not None and n.string in {'<', '>', '>>'} and
                n.start == token.end and token.string in _REDIRECT_NAMES):
            # looks like a redirect to me!
            e = n.end
            string += n.string
            n2 = next(stream, None)
            if n2 is not None and n2.string == '&' and n2.start == n.end:
                string += n2.string
                e = n2.end
                n2 = next(stream, None)
            if n2 is not None:
                if (n2.start == e and
                        (n2.type == tokenize.NUMBER or
                            (n2.type == tokenize.NAME and
                             n2.string in _REDIRECT_NAMES))):
                    string += n2.string
                    state['last'] = n2
                    yield _new_token('IOREDIRECT', string, token.start)
                else:
                    state['last'] = n
                    yield _new_token('IOREDIRECT', string, token.start)
                    yield from handle_token(state, n2, stream)
            else:
                state['last'] = n
                yield _new_token('IOREDIRECT', string, token.start)
        else:
            yield _new_token('NAME', token.string, token.start)
            if n is not None:
                yield from handle_token(state, n, stream)


def _make_special_handler(token_type, extra_check=lambda x: True):
    def inner_handler(state, token, stream):
        state['last'] = token
        if state['pymode'][-1][0]:
            yield _new_token(token_type, token.string, token.start)
        else:
            # subprocess mode
            n = next(stream, None)
            string = token.string
            if (n is not None and
                    n.string in {'<', '>', '>>'} and
                    n.start == token.end):
                e = n.end
                string += n.string
                n2 = next(stream, None)
                if n2 is not None and n2.string == '&' and n2.start == n.end:
                    state['last'] = n2
                    string += n2.string
                    e = n2.end
                    n2 = next(stream, None)
                if n2 is not None:
                    if (n2.start == e and
                            (n2.type == tokenize.NUMBER or
                                (n2.type == tokenize.NAME and
                                 n2.string in _REDIRECT_NAMES))):
                        string += n2.string
                        state['last'] = n2
                        yield _new_token('IOREDIRECT', string, token.start)
                    else:
                        state['last'] = n
                        yield _new_token('IOREDIRECT', string, token.start)
                        yield from handle_token(state, n2, stream)
                else:
                    state['last'] = n
                    yield _new_token('IOREDIRECT', string, token.start)
            else:
                yield _new_token(token_type, token.string, token.start)
                if n is not None:
                    yield from handle_token(state, n, stream)
    return inner_handler


handle_number = _make_special_handler('NUMBER')
"""Function for handling number tokens"""

handle_ampersand = _make_special_handler('AMPERSAND')
"""Function for handling ampersand tokens"""


def handle_dollar(state, token, stream):
    """
    Function for generating PLY tokens associated with ``$``.
    """
    n = next(stream, None)

    if n is None:
        m = "missing token after $"
        yield _new_token("ERRORTOKEN", m, token.start)
    elif n.start != token.end:
        m = "unexpected whitespace after $"
        yield _new_token("ERRORTOKEN", m, token.start)
    elif n.type == tokenize.NAME:
        state['last'] = n
        yield _new_token('DOLLAR_NAME', '$' + n.string, token.start)
    elif n.type == tokenize.OP and n.string == '(':
        state['pymode'].append((False, '$(', ')', token.start))
        state['last'] = n
        yield _new_token('DOLLAR_LPAREN', '$(', token.start)
    elif n.type == tokenize.OP and n.string == '[':
        state['pymode'].append((False, '$[', ']', token.start))
        state['last'] = n
        yield _new_token('DOLLAR_LBRACKET', '$[', token.start)
    elif n.type == tokenize.OP and n.string == '{':
        state['pymode'].append((True, '${', '}', token.start))
        state['last'] = n
        yield _new_token('DOLLAR_LBRACE', '${', token.start)
    else:
        e = 'expected NAME, (, [, or {{ after $, but got {0}'
        m = e.format(n)
        yield _new_token("ERRORTOKEN", m, token.start)


def handle_at(state, token, stream):
    """
    Function for generating PLY tokens associated with ``@``.
    """
    n = next(stream, None)

    if n is None:
        state['last'] = token
        m = "missing token after @"
        yield _new_token("ERRORTOKEN", m, token.start)
    elif n.type == tokenize.OP and n.string == '(' and \
            n.start == token.end:
        state['pymode'].append((True, '@(', ')', token.start))
        state['last'] = n
        yield _new_token('AT_LPAREN', '@(', token.start)
    else:
        state['last'] = token
        yield _new_token('AT', '@', token.start)
        yield from handle_token(state, n, stream)


def handle_question(state, token, stream):
    """
    Function for generating PLY tokens for help and superhelp
    """
    n = next(stream, None)

    if n is not None and n.type == tokenize.ERRORTOKEN and \
            n.string == '?' and n.start == token.end:
        state['last'] = n
        yield _new_token('DOUBLE_QUESTION', '??', token.start)
    else:
        state['last'] = token
        yield _new_token('QUESTION', '?', token.start)
        if n is not None:
            yield from handle_token(state, n, stream)


def handle_backtick(state, token, stream):
    """
    Function for generating PLY tokens representing regex globs.
    """
    n = next(stream, None)

    found_match = False
    sofar = '`'
    while n is not None:
        sofar += n.string
        if n.type == tokenize.ERRORTOKEN and n.string == '`':
            found_match = True
            break
        elif n.type == tokenize.NEWLINE or n.type == tokenize.NL:
            break
        n = next(stream, None)
    if found_match:
        state['last'] = n
        yield _new_token('REGEXPATH', sofar, token.start)
    else:
        state['last'] = token
        e = "Could not find matching backtick for regex on line {0}"
        m = e.format(token.start[0])
        yield _new_token("ERRORTOKEN", m, token.start)


def handle_lparen(state, token, stream):
    """
    Function for handling ``(``
    """
    state['pymode'].append((True, '(', ')', token.start))
    state['last'] = token
    yield _new_token('LPAREN', '(', token.start)


def handle_lbrace(state, token, stream):
    """
    Function for handling ``{``
    """
    state['pymode'].append((True, '{', '}', token.start))
    state['last'] = token
    yield _new_token('LBRACE', '{', token.start)


def handle_lbracket(state, token, stream):
    """
    Function for handling ``[``
    """
    state['pymode'].append((True, '[', ']', token.start))
    state['last'] = token
    yield _new_token('LBRACKET', '[', token.start)


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


def handle_rparen(state, token, stream):
    """
    Function for handling ``)``
    """
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RPAREN', ')', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_rbrace(state, token, stream):
    """
    Function for handling ``}``
    """
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RBRACE', '}', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_rbracket(state, token, stream):
    """
    Function for handling ``]``
    """
    e = _end_delimiter(state, token)
    if e is None:
        state['last'] = token
        yield _new_token('RBRACKET', ']', token.start)
    else:
        yield _new_token('ERRORTOKEN', e, token.start)


def handle_error_space(state, token, stream):
    """
    Function for handling special whitespace characters in subprocess mode
    """
    if not state['pymode'][-1][0]:
        state['last'] = token
        yield _new_token('WS', token.string, token.start)
    else:
        yield from []


def handle_error_token(state, token, stream):
    """
    Function for handling error tokens
    """
    state['last'] = token
    if not state['pymode'][-1][0]:
        typ = 'NAME'
    else:
        typ = 'ERRORTOKEN'
    yield _new_token(typ, token.string, token.start)


def handle_ignore(state, token, stream):
    """
    Function for handling tokens that should be ignored
    """
    yield from []


special_handlers = {
    tokenize.NL: handle_ignore,
    tokenize.COMMENT: handle_ignore,
    tokenize.ENCODING: handle_ignore,
    tokenize.ENDMARKER: handle_ignore,
    tokenize.NAME: handle_name,
    tokenize.NUMBER: handle_number,
    tokenize.ERRORTOKEN: handle_error_token,
    (tokenize.OP, '&'): handle_ampersand,
    (tokenize.OP, '@'): handle_at,
    (tokenize.OP, '('): handle_lparen,
    (tokenize.OP, ')'): handle_rparen,
    (tokenize.OP, '{'): handle_lbrace,
    (tokenize.OP, '}'): handle_rbrace,
    (tokenize.OP, '['): handle_lbracket,
    (tokenize.OP, ']'): handle_rbracket,
    (tokenize.ERRORTOKEN, '$'): handle_dollar,
    (tokenize.ERRORTOKEN, '`'): handle_backtick,
    (tokenize.ERRORTOKEN, '?'): handle_question,
    (tokenize.ERRORTOKEN, ' '): handle_error_space,
}
"""
Mapping from ``tokenize`` tokens (or token types) to the proper function for
generating PLY tokens from them.  In addition to yielding PLY tokens, these
functions may manipulate the Lexer's state.
"""


def handle_token(state, token, stream):
    """
    General-purpose token handler.  Makes use of ``token_map`` or
    ``special_map`` to yield one or more PLY tokens from the given input.

    Parameters
    ----------

    state :
        The current state of the lexer, including information about whether
        we are in Python mode or subprocess mode, which changes the lexer's
        behavior
    token :
        The token (from ``tokenize``) currently under consideration
    stream :
        A generator from which more tokens can be grabbed if necessary
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
        yield from special_handlers[(typ, st)](state, token, stream)
    elif (typ, st) in token_map:
        state['last'] = token
        yield _new_token(token_map[(typ, st)], st, token.start)
    elif typ in special_handlers:
        yield from special_handlers[typ](state, token, stream)
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
    tokstream = tokenize.tokenize(BytesIO(s.encode('utf-8')).readline)
    state = {'indents': [0], 'pymode': [(True, '', '', (0, 0))], 'last': None}
    while True:
        try:
            token = next(tokstream)
            yield from handle_token(state, token, tokstream)
        except StopIteration:
            if len(state['pymode']) > 1:
                pm, o, m, p = state['pymode'][-1]
                l, c = p
                e = 'Unmatched "{}" at line {}, column {}'
                yield _new_token('ERRORTOKEN', e.format(o, l, c), (0, 0))
            break
        except tokenize.TokenError as e:
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
        'NUMBER',                # numbers
        'WS',                    # whitespace in subprocess mode
        'AMPERSAND',             # &
        'REGEXPATH',             # regex escaped with backticks
        'IOREDIRECT',            # subprocess io redirection token
        'LPAREN', 'RPAREN',      # ( )
        'LBRACKET', 'RBRACKET',  # [ ]
        'LBRACE', 'RBRACE',      # { }
        'AT',                    # @
        'QUESTION',              # ?
        'DOUBLE_QUESTION',       # ??
        'AT_LPAREN',             # @(
        'DOLLAR_NAME',           # $NAME
        'DOLLAR_LPAREN',         # $(
        'DOLLAR_LBRACE',         # ${
        'DOLLAR_LBRACKET',       # $[
    ) + tuple(i.upper() for i in kwlist) + tuple(i.upper() for i in future_kwlist)
