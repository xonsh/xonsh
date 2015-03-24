from __future__ import print_function, unicode_literals
import re
import sys
import tokenize

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

#operators
op_map = {
        # punctuation
        '(': 'LPAREN', ')': 'RPAREN', '[': 'LBRACKET', ']': 'RBRACKET',
        '{': 'LBRACE', '}': 'RBRACE', ',': 'COMMA', '.': 'PERIOD', ';': 'SEMI',
        ':': 'COLON',
        #basic operators
        '+': 'PLUS', '-': 'MINUS', '*': 'TIMES', '/': 'DIVIDE', 
        '//': 'DOUBLEDIV', '%': 'MOD', '**': 'POW', '|': 'PIPE', 
        '&': 'AMPERSAND', '~': 'TILDE', '^': 'XOR', '<<': 'LSHIFT', 
        '>>': 'RSHIFT', '<': 'LT', '<=': 'LE', '>': 'GT', '>=': 'GE', 
        '==': 'EQ', '!=': 'NE','->': 'RARROW',
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
token_map[tokenize.ENDMARKER] = 'ENDMARKER'

def handle_indent(state, token, stream):
    level = len(token.string)
    if token.type == tokenize.DEDENT:
        state['indents'].pop()
        yield _new_token(state, 'DEDENT', ' '*state['indents'][-1], token.start[0], token.start[1])
    elif token.type == tokenize.INDENT:
        #moving forward
        state['indents'].append(level)
        yield _new_token(state, 'INDENT', token.string, token.start[0], token.start[1])

def handle_dollar(state, token, stream):
    try:
        n = next(stream)
    except:
        raise Exception("missing token after $")

    if n.start != token.end:
        raise Exception("unexpected whitespace after $")

    if n.type == tokenize.NAME:
        yield _new_token(state, 'DOLLAR_NAME', '$' + n.string, token.start[0], token.start[1])
    elif n.type == tokenize.OP and n.string == '(':
        yield _new_token(state, 'DOLLAR_LPAREN', '$(', token.start[0], token.start[1])
    elif n.type == tokenize.OP and n.string == '[':
        yield _new_token(state, 'DOLLAR_LBRACKET', '$[', token.start[0], token.start[1])
    elif n.type == tokenize.OP and n.string == '{':
        yield _new_token(state, 'DOLLAR_LBRACE', '${', token.start[0], token.start[1])
    else:
        e = 'expected NAME, (, [, or {{ after $, but got {0}'
        raise Exception(e.format(n))

def handle_at(state, token, stream):
    try:
        n = next(stream)
    except:
        raise Exception("missing token after @")
    
    if n.type == tokenize.OP and n.string == '(' and \
            n.start == token.end:
        yield _new_token(state, 'AT_LPAREN', '@(', token.start[0], token.start[1])
    else:
        yield _new_token(state, 'AT', '@', token.start[0], token.start[1])
        for i in handle_token(state, n, stream):
            yield i

def handle_question(state, token, stream):
    try:
        n = next(stream)
    except:
        n = None

    if n.type == tokenize.ERRORTOKEN and n.string == '?' and \
            n.start == token.end:
        yield _new_token(state, 'DOUBLE_QUESTION', '??', token.start[0], token.start[1])
    else:
        yield _new_token(state, 'QUESTION', '?', token.start[0], token.start[1])
        for i in handle_token(state, n, stream):
            yield i

def handle_backtick(state, token, stream):
    try:
        n = next(stream)
    except:
        n = None

    found_match = False
    sofar = ''
    while n is not None:
        if n.type == tokenize.ERRORTOKEN and n.string == '`':
            found_match = True
            break
        else:
            sofar += n.string
        try:
            n = next(stream)
        except:
            n = None
    if found_match:
        yield _new_token(state, 'REGEXPATH', sofar, token.start[0], token.start[1])
    else:
        e = "Could not find matching backtick for regex on line {0}"
        raise Exception(e.format(token.start[0]))

def handle_newline(state, token, stream):
    try:
        n = next(stream)
    except:
        n = None

    yield _new_token(state, 'NEWLINE', '\n', token.start[0], token.start[1])

    if n is not None:
        if n.type != tokenize.ENDMARKER:
            for i in handle_token(state, n, stream):
                yield i
        

special_handlers = {
    tokenize.ENCODING: lambda s,t,st: [],
    tokenize.NEWLINE: handle_newline,
    (tokenize.ERRORTOKEN, '$'): handle_dollar,
    (tokenize.ERRORTOKEN, '`'): handle_backtick,
    (tokenize.ERRORTOKEN, '?'): handle_question,
    (tokenize.OP, '@'): handle_at,
    tokenize.INDENT: handle_indent,
    tokenize.DEDENT: handle_indent
}

def handle_token(state, token, stream):
    typ = token.type
    st = token.string
    print('trying', typ, st)
    if (typ, st) in token_map:
        yield _new_token(state, token_map[(typ, st)], st, token.start[0], token.start[1])
    elif typ in token_map:
        yield _new_token(state, token_map[typ], st, token.start[0], token.start[1])
    elif (typ, st) in special_handlers:
        for i in special_handlers[(typ, st)](state, token, stream):
            yield i
    elif typ in special_handlers:
        for i in special_handlers[typ](state, token, stream):
            yield i
    else:
        raise Exception('Unexpected token: {0}'.format(token))

def preprocess_tokens(tokstream):
    #tokstream = clear_NL(tokstream)
    state = {'indents': [0], 'lexpos': 0}
    for token in tokstream:
        for i in handle_token(state, token, tokstream):
            yield i

def clear_NL(tokstream):
    for i in tokstream:
        if i.type != tokenize.NL:
            yield i

from io import BytesIO
def tok(s):
    return iter(tokenize.tokenize(BytesIO(s.encode('utf-8')).readline))


#synthesize a new PLY token
def _new_token(state, type, value, lineno, col):
    o = LexToken()
    o.type = type
    o.value = value
    o.lineno = lineno
    o.lexpos = state['lexpos']
    o.col = col
    print('col',col)
    state['lexpos'] += 1
    return o

def anyof(*regexes):
    return '(' + '|'.join(regexes) + ')'

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
        self.lexer = None
        self.indent = ''
        self.in_py_mode = [True]

    def build(self, **kwargs):
        """Part of the PLY lexer API."""
        self.lexer = lex.lex(object=self, **kwargs)
        self.reset()

    def reset(self):
        self.lexer.lineno = 1
        self.indent = ''
        self.last = None
        self.in_py_mode = [True]
        self.in_parens = [False]

    @property
    def lineno(self):
        if self.lexer is not None:
            return self.lexer.lineno

    @lineno.setter
    def lineno(self, value):
        if self.lexer is not None:
            self.lexer.lineno = value

    def input(self, s):
        """Calls the lexer on the string s."""
        print('code:\n',repr(s))
        self.token_stream = preprocess_tokens(tok(s))

    def token(self):
        """Retrieves the next token."""
        try:
            o = next(self.token_stream)
            print(o)
            return o
        except:
            return None

    def token_col(self, token):
        """Discovers the token column number."""
        offset = self.lexer.lexdata.rfind('\n', 0, token.lexpos)
        return token.lexpos - offset

    def _error(self, msg, token):
        location = self._make_tok_location(token)
        self.errfunc(msg, location[0], location[1])
        self.lexer.skip(1)

    def _make_tok_location(self, token):
        return (token.lineno, self.token_col(token))

    def __iter__(self):
        t = self.token()
        while t is not None:
            yield t
            t = self.token()

    #
    # Python keywords
    #
    pykeywords = ('AND', 'AS', 'ASSERT', 'BREAK', 'CLASS', 'CONTINUE', 'DEF', 
        'DEL', 'ELIF', 'ELSE', 'EXCEPT', 
        #'EXEC', 
        'FINALLY', 'FOR', 'FROM', 
        'GLOBAL', 'IMPORT', 'IF', 'IN', 'IS', 'LAMBDA', 'NONLOCAL', 'NOT', 
        'OR', 'PASS', 'RAISE', 'RETURN', 'TRY', 'WHILE', 'WITH', 'YIELD',)

    pykeyword_map = {k.lower(): k for k in pykeywords}

    #
    # All the tokens recognized by the lexer
    #
    tokens = pykeywords + (
        # Misc
        'NAME', 'INDENT', 'DEDENT', 'NEWLINE', 'ENDMARKER', 
        'NONE', 'TRUE', 'FALSE',

        # literals
        'NUMBER', 'STRING',

        # Basic Operators
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'DOUBLEDIV', 'MOD', 'POW', 
        'PIPE', 'AMPERSAND', 'TILDE', 'XOR', 'LSHIFT', 'RSHIFT',
        #'LOGIC_OR', 
        #'LOGIC_AND', 
        'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',
        #'LARROW',
        'RARROW',

        # Assignment Operators
        'EQUALS', 'PLUSEQUAL', 'MINUSEQUAL', 'TIMESEQUAL', 'DIVEQUAL', 
        'MODEQUAL', 'POWEQUAL', 'LSHIFTEQUAL', 'RSHIFTEQUAL', 'AMPERSANDEQUAL', 
        'XOREQUAL', 'PIPEEQUAL', 'DOUBLEDIVEQUAL',

        # Command line
        #'CLI_OPTION', 
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

    #
    # Token Regexes
    #
    identifier = r'[a-zA-Z_][0-9a-zA-Z_]*'
    dollar = r'\$'

    int_literal = '\d+'
    hex_literal = '0[xX][0-9a-fA-F]+'
    oct_literal = '0[oO]?[0-7]+'
    bin_literal = '0[bB]?[0-1]+'

    # string literals
    triple_single_string = r"'''((\\(.|\n))|([^'\\])|('(?!''))|\n)*'''"
    triple_double_string = r'"""((\\(.|\n))|([^"\\])|("(?!""))|\n)*"""'
    single_single_string = r"'((\\(.|\n))|([^'\\]))*'"
    single_double_string = r'"((\\(.|\n))|([^"\\]))*"'
    triple_string = anyof(triple_single_string, triple_double_string) 
    single_string = anyof(single_single_string, single_double_string)
    string_literal = anyof(triple_string, single_string)
    raw_string_literal = '[Rr]' + string_literal
    unicode_literal = '[Uu]' + string_literal 
    bytes_literal = '[Bb]' + string_literal

    # floating point
    float_exponent = r"(?:[eE][-+]?[0-9]+)"
    float_mantissa = r"(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.)"
    float_literal = ('((((' + float_mantissa + ')' + float_exponent + 
                     '?)|([0-9]+' + float_exponent + ')))')
    imag_literal = '(' + r'[0-9]+[jJ]' + '|' + float_literal + r'[jJ]' + ')'

    #
    # Rules 
    #

    # Command line
    def t_INDENT(self, t):
        r'[ \t]+'
        last = self.last
        if not self.in_py_mode[-1]:
            return t
        elif last is not None and last.type != 'NEWLINE':
            return  # returns None to skip internal whitespace
        i = self.indent
        v = t.value
        if len(i) > len(v):
            if not i.startswith(v):
                self._error("indentation level does not match previous level", t)
            t.type = 'DEDENT'
        elif not v.startswith(i):
            self._error("indentation level does not match previous level", t)
        self.indent = v
        t.lexer.lineno += 1
        return t

    t_ENDMARKER = r'\x03'

    # Newlines
    def t_NEWLINE(self, t):
        r'\n'
        if self.in_parens[-1]:
            t.lexer.lineno += 1
            return None
        else:
            return t

    #
    # Ignore internal whitespace based on parentherical scope
    #

    def t_AT_LPAREN(self, t):
        r'@\('
        self.in_parens.append(True)
        self.in_py_mode.append(True)
        return t

    def t_DOLLAR_LPAREN(self, t):
        r'\$\('
        self.in_parens.append(True)
        self.in_py_mode.append(False)
        return t

    def t_LPAREN(self, t):
        r'\('
        self.in_parens.append(True)
        self.in_py_mode.append(True)
        return t

    def t_RPAREN(self, t):
        r'\)'
        self.in_parens.pop()
        self.in_py_mode.pop()
        return t

    def t_DOLLAR_LBRACE(self, t):
        r'\$\{'
        self.in_parens.append(True)
        self.in_py_mode.append(True)
        return t

    def t_LBRACE(self, t):
        r'\{'
        self.in_parens.append(True)
        self.in_py_mode.append(True)
        return t

    def t_RBRACE(self, t):
        r'\}'
        self.in_parens.pop()
        self.in_py_mode.pop()
        return t

    def t_DOLLAR_LBRACKET(self, t):
        r'\$\['
        self.in_parens.append(True)
        self.in_py_mode.append(False)
        return t

    def t_LBRACKET(self, t):
        r'\['
        self.in_parens.append(True)
        self.in_py_mode.append(True)
        return t

    def t_RBRACKET(self, t):
        r'\]'
        self.in_parens.pop()
        self.in_py_mode.pop()
        return t

    # Basic Operators
    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_TIMES = r'\*'
    t_DIVIDE = r'/'
    t_DOUBLEDIV = r'//'
    t_MOD = r'%'
    t_POW = r'\*\*'
    t_PIPE = r'\|'
    t_AMPERSAND = r'&'
    t_TILDE = r'~'
    t_XOR = r'\^'
    t_LSHIFT = r'<<'
    t_RSHIFT = r'>>'
    #t_LOGIC_OR = r'\|\|'
    #t_LOGIC_AND = r'&&'
    t_LT = r'<'
    t_GT = r'>'
    t_LE = r'<='
    t_GE = r'>='
    t_EQ = r'=='
    t_NE = r'!='
    #t_LARROW = r'<-'
    t_RARROW = r'->'

    # Assignment Operators
    t_EQUALS = r'='
    t_PLUSEQUAL = r'\+='
    t_MINUSEQUAL = r'-='
    t_TIMESEQUAL = r'\*='
    t_DIVEQUAL = r'/='
    t_MODEQUAL = r'%='
    t_POWEQUAL = r'\*\*='
    t_LSHIFTEQUAL = r'<<='
    t_RSHIFTEQUAL = r'>>='
    t_AMPERSANDEQUAL = r'&='
    t_PIPEEQUAL = r'\|='
    t_XOREQUAL = r'\^='
    t_DOUBLEDIVEQUAL = r'//='
    t_DOLLAR = dollar
    t_REGEXPATH = r'`[^`]*`'

    def t_DOUBLE_QUESTION(self, t):
        r'\?\?'
        return t

    t_QUESTION = r'\?'

    # Delimeters
    #t_LPAREN = r'\('
    #t_RPAREN = r'\)'
    #t_LBRACKET = r'\['
    #t_RBRACKET = r'\]'
    #t_LBRACE = r'\{'
    #t_RBRACE = r'\}'
    t_COMMA = r','
    t_PERIOD = r'\.'
    t_SEMI = r';'
    t_COLON = r':'
    t_AT = r'@'
    t_ELLIPSIS = r'\.\.\.'

    def t_COMMENT(self, t):
        r'\#.*'
        return

    #
    # Literals
    #

    # strings, functions to ensure correct ordering

    @TOKEN(string_literal)
    def t_STRING_LITERAL(self, t):
        return t

    # float literal must come before int literals

    @TOKEN(imag_literal)
    def t_IMAG_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = eval(t.value)
        return t

    @TOKEN(float_literal)
    def t_FLOAT_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = float(t.value)
        return t

    # ints, functions to ensure correct ordering

    @TOKEN(hex_literal)
    def t_HEX_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = int(t.value, 16)
        return t

    @TOKEN(oct_literal)
    def t_OCT_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = int(t.value, 8)
        return t

    @TOKEN(bin_literal)
    def t_BIN_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = int(t.value, 2)
        return t

    @TOKEN(int_literal)
    def t_INT_LITERAL(self, t):
        if self.in_py_mode[-1]:
            t.value = int(t.value)
        return t

    def t_NONE(self, t):
        r'None'
        if self.in_py_mode[-1]:
            t.value = None
        return t

    def t_TRUE(self, t):
        r'True'
        if self.in_py_mode[-1]:
            t.value = True
        return t

    def t_FALSE(self, t):
        r'False'
        if self.in_py_mode[-1]:
            t.value = False
        return t

    # Extra
    @TOKEN(identifier)
    def t_NAME(self, t):
        if self.in_py_mode[-1] and t.value in self.pykeyword_map:
            t.type = self.pykeyword_map[t.value]
        return t

    def t_error(self, t):
        msg = 'Invalid token {0!r}'.format(t.value[0])
        self._error(msg, t)

