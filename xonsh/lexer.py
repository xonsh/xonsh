from __future__ import print_function, unicode_literals
import re
import sys

from ply import lex
from ply.lex import TOKEN


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
        self.lexer.input(s)

    def token(self):
        """Retrieves the next token."""
        self.last = self.lexer.token()
        return self.last

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
        'INT_LITERAL', 'HEX_LITERAL', 'OCT_LITERAL', 'BIN_LITERAL',
        'FLOAT_LITERAL', 'STRING_LITERAL', 'RAW_STRING_LITERAL',
        'BYTES_LITERAL', 'UNICODE_LITERAL',

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
        'DOLLAR',                # $
        'QUESTION',              # ?
        'DOUBLE_QUESTION',       # ??
        'COMMENT',               # #
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
    single_string_literal = '(?:\'(?:[^\'\\n\\r\\\\]|(?:\'\')|(?:\\\\x[0-9a-fA-F]+)|(?:\\\\.))*\')'
    double_string_literal = '(?:"(?:[^"\\n\\r\\\\]|(?:"")|(?:\\\\x[0-9a-fA-F]+)|(?:\\\\.))*")'
    string_literal = single_string_literal + '|' + double_string_literal
    raw_string_literal = 'r' + single_string_literal + '|r' + double_string_literal
    unicode_literal = 'u' + single_string_literal + '|u' + double_string_literal
    bytes_literal = 'b' + single_string_literal + '|b' + double_string_literal

    # floating point
    float_exponent = r"(?:[eE][-+]?[0-9]+)"
    float_mantissa = r"(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.)"
    float_literal = ('((((' + float_mantissa + ')' + float_exponent + 
                     '?)|([0-9]+' + float_exponent + ')))')

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
        return t

    t_ENDMARKER = r'\x03'

    # Newlines
    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count("\n")
        return t

    #
    # Ignore internal whitespace based on parentherical scope
    #
    
    def t_DOLLAR_LPAREN(self, t):
        r'\$\('
        self.in_py_mode.append(False)
        return t

    def t_LPAREN(self, t):
        r'\('
        self.in_py_mode.append(True)
        return t

    def t_RPAREN(self, t):
        r'\)'
        self.in_py_mode.pop()
        return t

    def t_DOLLAR_LBRACE(self, t):
        r'\$\{'
        self.in_py_mode.append(True)
        return t

    def t_LBRACE(self, t):
        r'\{'
        self.in_py_mode.append(True)
        return t

    def t_RBRACE(self, t):
        r'\}'
        self.in_py_mode.pop()
        return t

    def t_DOLLAR_LBRACKET(self, t):
        r'\$\['
        self.in_py_mode.append(False)
        return t

    def t_LBRACKET(self, t):
        r'\['
        self.in_py_mode.append(True)
        return t

    def t_RBRACKET(self, t):
        r'\]'
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
    t_ignore_COMMENT = r'\#.*$'
    t_ELLIPSIS = r'\.\.\.'

    #
    # Literals
    #

    # strings, functions to ensure correct ordering

    @TOKEN(string_literal)
    def t_STRING_LITERAL(self, t):
        return t

    @TOKEN(raw_string_literal)
    def t_RAW_STRING_LITERAL(self, t):
        return t

    @TOKEN(unicode_literal)
    def t_UNICODE_LITERAL(self, t):
        return t

    @TOKEN(bytes_literal)
    def t_BYTES_LITERAL(self, t):
        return t

    # float literal must come before int literals

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

