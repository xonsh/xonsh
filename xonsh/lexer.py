from __future__ import print_function, unicode_literals
import re
import sys

from ply import lex
from ply.lex import TOKEN


class Lexer(object):
    """Implements a lexer for the xonsh language.
    """
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

    def build(self, **kwargs):
        """Part of the PLY lexer API."""
        self.lexer = lex.lex(object=self, **kwargs)

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
        for t in self.lexer:
            yield t

    #
    # Python keywords
    #
    pykeywords = ('AND', 'AS', 'ASSERT', 'BREAK', 'CLASS', 'CONTINUE', 'DEF', 
        'DEL', 'ELIF', 'ELSE', 'EXCEPT', 'EXEC', 'FINALLY', 'FOR', 'FROM', 
        'GLOBAL', 'IMPORT', 'IF', 'IN', 'IS', 'LAMBDA', 'NONLOCAL', 'NOT', 
        'OR', 'PASS', 'RAISE', 'TRY', 'WHILE', 'WITH', 'YIELD',)

    pykeyword_map = {k.lower(): k for k in pykeywords}

    #
    # All the tokens recognized by the lexer
    #
    tokens = pykeywords + (
        # Misc
        'ID', 'INDENT', 'NEWLINE', 'WHITESPACE',

        # literals
        'INT_LITERAL', 'HEX_LITERAL', 'OCT_LITERAL', 'BIN_LITERAL',
        'FLOAT_LITERAL', 'STRING_LITERAL', 'RAW_STRING_LITERAL',
        'BYTES_LITERAL', 'UNICODE_LITERAL',

        # Basic Operators
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD', 'POW', 
        'PIPE', 'AMPERSAND', 'TILDE', 'XOR', 'LSHIFT', 'RSHIFT',
        'LOGIC_OR', 'LOGIC_AND', 'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',

        # Assignment Operators
        'EQUALS', 'PLUSEQUAL', 'MINUSEQUAL', 'TIMESEQUAL', 'DIVEQUAL', 
        'MODEQUAL', 'POWEQUAL', 'LSHIFTEQUAL','RSHIFTEQUAL', 'AMPERSANDEQUAL', 
        'XOREQUAL', 'PIPEEQUAL',

        # Command line
        'CLI_OPTION', 

        # Delimeters
        'LPAREN', 'RPAREN',      # ( )
        'LBRACKET', 'RBRACKET',  # [ ]
        'LBRACE', 'RBRACE',      # { }
        'COMMA', 'PERIOD',       # . ,
        'SEMI', 'COLON',         # ; :
        'AT', 'DOLLAR',          # @ $
        'COMMENT',               # #

        # Ellipsis (...)
        'ELLIPSIS',
        )

    #
    # Token Regexes
    #
    identifier = r'[a-zA-Z_$][0-9a-zA-Z_$]*'

    int_literal = '\d+'
    hex_literal = '0[xX][0-9a-fA-F]+'
    oct_literal = '0[oO]?[0-7]+'
    bin_literal = '0[bB]?[0-1]+'

    # string literals
    #string_literal = r'''(\"\"\"|\'\'\'|\"|\')((?<!\\)\\\1|.)*?\1'''
    string_literal = r'(?:"(?:[^"\\n\\r\\\\]|(?:"")|(?:\\\\x[0-9a-fA-F]+)|(?:\\\\.))*")|(?:\'(?:[^\'\\n\\r\\\\]|(?:\'\')|(?:\\\\x[0-9a-fA-F]+)|(?:\\\\.))*\')'
    raw_string_literal = 'r'+string_literal
    unicode_literal = 'u'+string_literal
    bytes_literal = 'b'+string_literal

    # floating point
    float_exponent = r"""([eE][-+]?[0-9]+)"""
    float_matissa = r"""([0-9]*\.[0-9]+)|([0-9]+\.)"""
    float_literal = float_matissa + float_exponent + '?'

    #
    # Rules 
    #
    t_INDENT = r'^[ \t]+'
    t_ignore_WHITESPACE = r'[ \t]+'

    # Newlines
    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count("\n")

    # Python Keywords
    t_AND = r'and'
    t_AS = r'as'
    t_ASSERT = r'assert' 
    t_BREAK = r'break'
    t_CLASS = r'class'
    t_CONTINUE = r'continue'
    t_DEF = r'def' 
    t_DEL = r'delete' 
    t_ELIF = 'elif'
    t_ELSE = r'else'
    t_EXCEPT = r'except'
    t_EXEC = r'exec'
    t_FINALLY = 'finally'
    t_FOR = r'for'
    t_FROM = r'from'
    t_GLOBAL = r'global'
    t_IMPORT = r'import'
    t_IF = r'if'
    t_IN = r'in'
    t_IS = r'is'
    t_LAMBDA = r'lambda'
    t_NONLOCAL = r'nonlocal'
    t_NOT = r'not'
    t_OR = r'or'
    t_PASS = r'pass'
    t_RAISE = r'raise'
    t_TRY = r'try'
    t_WHILE = r'while'
    t_WITH = r'with'
    t_YIELD = r'yield'

    # Basic Operators
    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_TIMES = r'\*'
    t_DIVIDE = r'/'
    t_MOD = r'%'
    t_POW = r'\*\*'
    t_PIPE = r'\|'
    t_AMPERSAND = r'&'
    t_TILDE = r'~'
    t_XOR = r'\^'
    t_LSHIFT = r'<<'
    t_RSHIFT = r'>>'
    t_LOGIC_OR = r'\|\|'
    t_LOGIC_AND = r'&&'
    t_LT = r'<'
    t_GT = r'>'
    t_LE = r'<='
    t_GE = r'>='
    t_EQ = r'=='
    t_NE = r'!='

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

    # Delimeters
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_LBRACE = r'\{'
    t_RBRACE = r'\}'
    t_COMMA = r','
    t_PERIOD = r'\.'
    t_SEMI = r';'
    t_COLON = r':'
    t_AT = r'@'
    t_DOLLAR = r'\$'
    t_COMMENT = r'\#.*$'
    t_ELLIPSIS = r'\.\.\.'

    #
    # Literals
    #

    # strings, functions to ensure correct ordering
    t_STRING_LITERAL = string_literal

    @TOKEN(raw_string_literal)
    def t_RAW_STRING_LITERAL(self, t):
        return t

    @TOKEN(unicode_literal)
    def t_UNICODE_LITERAL(self, t):
        return t

    @TOKEN(bytes_literal)
    def t_BYTES_LITERAL(self, t):
        return t

    
    t_FLOAT_LITERAL = float_literal

    # ints, functions to ensure correct ordering
    t_INT_LITERAL = int_literal

    @TOKEN(hex_literal)
    def t_HEX_LITERAL(self, t):
        return t

    @TOKEN(oct_literal)
    def t_OCT_LITERAL(self, t):
        return t

    @TOKEN(bin_literal)
    def t_BIN_LITERAL(self, t):
        return t

    # Extra

    @TOKEN(identifier)
    def t_ID(self, t):
        return t

    def t_error(self, t):
        msg = 'Invalid token {0!r}'.format(t.value[0])
        self._error(msg, t)

