from __future__ import print_function, unicode_literals
import re
import sys
import tokenize

from io import BytesIO
from keyword import kwlist

from ply import lex
from ply.lex import TOKEN, LexToken

# mapping from tokenize to PLY
# some keys are (type, name) tuples (for specific, e.g., keywords)
# some keys are just a type, for things like strings/names
# values are always a PLY token type
token_map = {}

# keywords
for kw in kwlist:
    token_map[(tokenize.NAME, kw)] = kw.upper()

# operators
op_map = {
        # punctuation
        ',': 'COMMA', '.': 'PERIOD', ';': 'SEMI', ':': 'COLON',
        '...': 'ELLIPSIS',
        # basic operators
        '+': 'PLUS', '-': 'MINUS', '*': 'TIMES', '/': 'DIVIDE',
        '//': 'DOUBLEDIV', '%': 'MOD', '**': 'POW', '|': 'PIPE',
        '&': 'AMPERSAND', '~': 'TILDE', '^': 'XOR', '<<': 'LSHIFT',
        '>>': 'RSHIFT', '<': 'LT', '<=': 'LE', '>': 'GT', '>=': 'GE',
        '==': 'EQ', '!=': 'NE', '->': 'RARROW',
        # assignment operators
        '=': 'EQUALS', '+=': 'PLUSEQUAL', '-=': 'MINUSEQUAL',
        '*=': 'TIMESEQUAL', '/=': 'DIVEQUAL', '%=': 'MODEQUAL',
        '**=': 'POWEQUAL', '<<=': 'LSHIFTEQUAL', '>>=': 'RSHIFTEQUAL',
        '&=': 'AMPERSANDEQUAL', '^=': 'XOREQUAL', '|=': 'PIPEEQUAL',
        '//=': 'DOUBLEDIVEQUAL',
}
for (op, type) in op_map.items():
    token_map[(tokenize.OP, op)] = type

token_map[tokenize.NAME] = 'NAME'
token_map[tokenize.NUMBER] = 'NUMBER'
token_map[tokenize.STRING] = 'STRING'
token_map[tokenize.NEWLINE] = 'NEWLINE'


def handle_indent(state, token, stream):
    level = len(token.string)
    state['last'] = token
    if token.type == tokenize.DEDENT:
        state['indents'].pop()
        yield _new_token('DEDENT', ' '*state['indents'][-1], token.start)
    elif token.type == tokenize.INDENT:
        state['indents'].append(level)
        yield _new_token('INDENT', token.string, token.start)


def handle_dollar(state, token, stream):
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
        state['pymode'].append(False)
        state['last'] = n
        yield _new_token('DOLLAR_LPAREN', '$(', token.start)
    elif n.type == tokenize.OP and n.string == '[':
        state['pymode'].append(False)
        state['last'] = n
        yield _new_token('DOLLAR_LBRACKET', '$[', token.start)
    elif n.type == tokenize.OP and n.string == '{':
        state['pymode'].append(True)
        state['last'] = n
        yield _new_token('DOLLAR_LBRACE', '${', token.start)
    else:
        e = 'expected NAME, (, [, or {{ after $, but got {0}'
        m = e.format(n)
        yield _new_token("ERRORTOKEN", m, token.start)


def handle_at(state, token, stream):
    n = next(stream, None)

    if n is None:
        state['last'] = token
        m = "missing token after @"
        yield _new_token("ERRORTOKEN", m, token.start)
    elif n.type == tokenize.OP and n.string == '(' and \
            n.start == token.end:
        state['pymode'].append(True)
        state['last'] = n
        yield _new_token('AT_LPAREN', '@(', token.start)
    else:
        state['last'] = token
        yield _new_token('AT', '@', token.start)
        yield from handle_token(state, n, stream)


def handle_question(state, token, stream):
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
    n = next(stream, None)

    found_match = False
    sofar = '`'
    while n is not None:
        sofar += n.string
        if n.type == tokenize.ERRORTOKEN and n.string == '`':
            found_match = True
            break
        try:
            n = next(stream)
        except:
            n = None
    if found_match:
        state['last'] = n
        yield _new_token('REGEXPATH', sofar, token.start)
    else:
        state['last'] = token
        e = "Could not find matching backtick for regex on line {0}"
        m = e.format(token.start[0])
        yield _new_token("ERRORTOKEN", m, token.start)


def handle_lparen(state, token, stream):
    state['pymode'].append(True)
    state['last'] = token
    yield _new_token('LPAREN', '(', token.start)


def handle_lbrace(state, token, stream):
    state['pymode'].append(True)
    state['last'] = token
    yield _new_token('LBRACE', '{', token.start)


def handle_lbracket(state, token, stream):
    state['pymode'].append(True)
    state['last'] = token
    yield _new_token('LBRACKET', '[', token.start)


def handle_rparen(state, token, stream):
    state['pymode'].pop()
    state['last'] = token
    yield _new_token('RPAREN', ')', token.start)


def handle_rbrace(state, token, stream):
    state['pymode'].pop()
    state['last'] = token
    yield _new_token('RBRACE', '}', token.start)


def handle_rbracket(state, token, stream):
    state['pymode'].pop()
    state['last'] = token
    yield _new_token('RBRACKET', ']', token.start)


def handle_error_space(state, token, stream):
    if not state['pymode'][-1]:
        state['last'] = token
        yield _new_token('WS', token.string, token.start)
    else:
        yield from []


def handle_ignore(state, token, stream):
    yield from []


special_handlers = {
    tokenize.COMMENT: handle_ignore,
    tokenize.ENCODING: handle_ignore,
    tokenize.ENDMARKER: handle_ignore,
    (tokenize.OP, '('): handle_lparen,
    (tokenize.OP, ')'): handle_rparen,
    (tokenize.OP, '['): handle_lbracket,
    (tokenize.OP, ']'): handle_rbracket,
    (tokenize.OP, '{'): handle_lbrace,
    (tokenize.OP, '}'): handle_rbrace,
    (tokenize.ERRORTOKEN, '$'): handle_dollar,
    (tokenize.ERRORTOKEN, '`'): handle_backtick,
    (tokenize.ERRORTOKEN, '?'): handle_question,
    (tokenize.OP, '@'): handle_at,
    (tokenize.ERRORTOKEN, ' '): handle_error_space,
    tokenize.INDENT: handle_indent,
    tokenize.DEDENT: handle_indent,
}


def handle_token(state, token, stream):
    typ = token.type
    st = token.string
    if not state['pymode'][-1]:
        if state['last'] is not None and state['last'].end != token.start:
            cur = token.start
            old = state['last'].end
            yield _new_token('WS', ' '*(cur[1]-old[1]), old)
    if (typ, st) in token_map:
        state['last'] = token
        yield _new_token(token_map[(typ, st)], st, token.start)
    elif typ in token_map:
        state['last'] = token
        yield _new_token(token_map[typ], st, token.start)
    elif (typ, st) in special_handlers:
        yield from special_handlers[(typ, st)](state, token, stream)
    elif typ in special_handlers:
        yield from special_handlers[typ](state, token, stream)
    else:
        m = "Unexpected token: {0}".format(token)
        yield _new_token("ERRORTOKEN", m, token.start)


def preprocess_tokens(tokstream):
    tokstream = clear_nl(tokstream)
    state = {'indents': [0], 'pymode': [True], 'last': None}
    for token in tokstream:
        yield from handle_token(state, token, tokstream)


def clear_nl(tokstream):
    for i in tokstream:
        if i.type != tokenize.NL:
            yield i


def single_error(exc):
    m = "{} (line {}, column {})".format(exc.msg, exc.lineno, exc.offset)
    yield _new_token("ERRORTOKEN", m, (0, 0))


def tok(s):
    try:
        return tokenize.tokenize(BytesIO(s.encode('utf-8')).readline)
    except Exception as e:
        return single_error(e)


# synthesize a new PLY token
def _new_token(type, value, pos):
    o = LexToken()
    o.type = type
    o.value = value
    o.lineno, o.lexpos = pos
    return o


COMMENT_REGEX = re.compile(r'#.*')


class Lexer(object):
    """Implements a lexer for the xonsh language."""

    def __init__(self, errfunc=lambda e, l, c: print(e)):
        """
        Parameters
        ----------
        errfunc : function, optional
            An error function callback. Accepts an error
            message, line and column as arguments.

        Attributes
        ----------
        lexer : a PLY lexer bound to self
        fname : str
            Filename
        last : token
            The last token seen.
        lineno : int
            The last line number seen.

        """
        self.errfunc = errfunc
        self.fname = ''
        self.last = None

    def build(self, **kwargs):
        """Part of the PLY lexer API."""
        pass

    def reset(self):
        pass

    def input(self, s):
        """Calls the lexer on the string s."""
        s = re.sub(COMMENT_REGEX, '', s)
        self.token_stream = preprocess_tokens(tok(s))

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
    # Python keywords
    #
    pykeywords = ('AND', 'AS', 'ASSERT', 'BREAK', 'CLASS', 'CONTINUE', 'DEF',
                  'DEL', 'ELIF', 'ELSE', 'EXCEPT', 'FINALLY', 'FOR', 'FROM',
                  'GLOBAL', 'IMPORT', 'IF', 'IN', 'IS', 'LAMBDA', 'NONLOCAL',
                  'NOT', 'OR', 'PASS', 'RAISE', 'RETURN', 'TRY', 'WHILE',
                  'WITH', 'YIELD',)

    pykeyword_map = {k.lower(): k for k in pykeywords}

    #
    # All the tokens recognized by the lexer
    #
    tokens = pykeywords + (
        # Misc
        'NAME', 'INDENT', 'DEDENT', 'NEWLINE', 'ENDMARKER',
        'NONE', 'TRUE', 'FALSE', 'WS',

        # literals
        'NUMBER', 'STRING',

        # Basic Operators
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'DOUBLEDIV', 'MOD', 'POW',
        'PIPE', 'AMPERSAND', 'TILDE', 'XOR', 'LSHIFT', 'RSHIFT',
        'LT', 'LE', 'GT', 'GE', 'EQ', 'NE', 'RARROW',

        # Assignment Operators
        'EQUALS', 'PLUSEQUAL', 'MINUSEQUAL', 'TIMESEQUAL', 'DIVEQUAL',
        'MODEQUAL', 'POWEQUAL', 'LSHIFTEQUAL', 'RSHIFTEQUAL', 'AMPERSANDEQUAL',
        'XOREQUAL', 'PIPEEQUAL', 'DOUBLEDIVEQUAL',

        # Command line
        'REGEXPATH',

        # Delimeters
        'LPAREN', 'RPAREN',      # ( )
        'LBRACKET', 'RBRACKET',  # [ ]
        'LBRACE', 'RBRACE',      # { }
        'COMMA', 'PERIOD',       # . ,
        'SEMI', 'COLON',         # ; :
        'AT',                    # @
        'QUESTION',              # ?
        'DOUBLE_QUESTION',       # ??
        'AT_LPAREN',             # @(
        'DOLLAR_NAME',           # $NAME
        'DOLLAR_LPAREN',         # $(
        'DOLLAR_LBRACE',         # ${
        'DOLLAR_LBRACKET',       # $[

        # Ellipsis (...)
        'ELLIPSIS',
        )
