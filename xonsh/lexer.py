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

    def build(self, **kwargs):
        """Part of the PLY lexer API.
        """
        self.lexer = lex.lex(object=self, **kwargs)

    @property
    def lineno(self):
        return self.lexer.lineno

    @lineno.setter
    def lineno(self, value)
        self.lexer.lineno = 1

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

    ######################--   PRIVATE   --######################

    ##
    ## Internal auxiliary methods
    ##
    def _error(self, msg, token):
        location = self._make_tok_location(token)
        self.error_func(msg, location[0], location[1])
        self.lexer.skip(1)

    def _make_tok_location(self, token):
        return (token.lineno, self.find_tok_column(token))

    ##
    ## Reserved keywords
    ##
    pykeywords = ('AND', 'AS', 'ASSERT', 'BREAK', 'CLASS', 'CONTINUE', 'DEF', 
        'DEL', 'ELIF', 'ELSE', 'EXCEPT', 'FINALLY', 'FOR', 'FROM', 'GLOBAL', 
        'IMPORT', 'IF', 'IN', 'IS', 'LAMBDA', 'NONLOCAL', 'NOT', 'OR', 'PASS', 
        'RAISE', 'TRY', 'WHILE', 'WITH', 'YIELD',)

    pykeyword_map = {k.lower(): k for k in pykeywords}

    ##
    ## All the tokens recognized by the lexer
    ##
    tokens = pykeywords + (
        # Identifiers
        'ID',

        # constants
        'INT_CONST_DEC', 'INT_CONST_OCT', 'INT_CONST_HEX',
        'FLOAT_CONST', 'HEX_FLOAT_CONST',

        # String literals
        'STRING_LITERAL',

        # Operators
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD',
        'OR', 'AND', 'NOT', 'XOR', 'LSHIFT', 'RSHIFT',
        'LOR', 'LAND', 'LNOT',
        'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',

        # Assignment
        'EQUALS', 'TIMESEQUAL', 'DIVEQUAL', 'MODEQUAL',
        'PLUSEQUAL', 'MINUSEQUAL',
        'LSHIFTEQUAL','RSHIFTEQUAL', 'ANDEQUAL', 'XOREQUAL',
        'OREQUAL',

        # Command line
        'OPTION', 

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

    ##
    ## Regexes for use in tokens
    ##
    ##

    # valid C identifiers (K&R2: A.2.3), plus '$' (supported by some compilers)
    identifier = r'[a-zA-Z_$][0-9a-zA-Z_$]*'

    hex_prefix = '0[xX]'
    hex_digits = '[0-9a-fA-F]+'

    # integer constants (K&R2: A.2.5.1)
    integer_suffix_opt = r'(([uU]ll)|([uU]LL)|(ll[uU]?)|(LL[uU]?)|([uU][lL])|([lL][uU]?)|[uU])?'
    decimal_constant = '(0'+integer_suffix_opt+')|([1-9][0-9]*'+integer_suffix_opt+')'
    octal_constant = '0[0-7]*'+integer_suffix_opt
    hex_constant = hex_prefix+hex_digits+integer_suffix_opt

    bad_octal_constant = '0[0-7]*[89]'

    # character constants (K&R2: A.2.5.2)
    # Note: a-zA-Z and '.-~^_!=&;,' are allowed as escape chars to support #line
    # directives with Windows paths as filenames (..\..\dir\file)
    # For the same reason, decimal_escape allows all digit sequences. We want to
    # parse all correct code, even if it means to sometimes parse incorrect
    # code.
    #
    simple_escape = r"""([a-zA-Z._~!=&\^\-\\?'"])"""
    decimal_escape = r"""(\d+)"""
    hex_escape = r"""(x[0-9a-fA-F]+)"""
    bad_escape = r"""([\\][^a-zA-Z._~^!=&\^\-\\?'"x0-7])"""

    escape_sequence = r"""(\\("""+simple_escape+'|'+decimal_escape+'|'+hex_escape+'))'
    cconst_char = r"""([^'\\\n]|"""+escape_sequence+')'
    char_const = "'"+cconst_char+"'"
    wchar_const = 'L'+char_const
    unmatched_quote = "('"+cconst_char+"*\\n)|('"+cconst_char+"*$)"
    bad_char_const = r"""('"""+cconst_char+"""[^'\n]+')|('')|('"""+bad_escape+r"""[^'\n]*')"""

    # string literals (K&R2: A.2.6)
    string_char = r"""([^"\\\n]|"""+escape_sequence+')'
    string_literal = '"'+string_char+'*"'
    wstring_literal = 'L'+string_literal
    bad_string_literal = '"'+string_char+'*'+bad_escape+string_char+'*"'

    # floating constants (K&R2: A.2.5.3)
    exponent_part = r"""([eE][-+]?[0-9]+)"""
    fractional_constant = r"""([0-9]*\.[0-9]+)|([0-9]+\.)"""
    floating_constant = '(((('+fractional_constant+')'+exponent_part+'?)|([0-9]+'+exponent_part+'))[FfLl]?)'
    binary_exponent_part = r'''([pP][+-]?[0-9]+)'''
    hex_fractional_constant = '((('+hex_digits+r""")?\."""+hex_digits+')|('+hex_digits+r"""\.))"""
    hex_floating_constant = '('+hex_prefix+'('+hex_digits+'|'+hex_fractional_constant+')'+binary_exponent_part+'[FfLl]?)'

    ##
    ## Lexer states: used for preprocessor \n-terminated directives
    ##
    states = (
        # ppline: preprocessor line directives
        #
        ('ppline', 'exclusive'),

        # pppragma: pragma
        #
        ('pppragma', 'exclusive'),
    )

    def t_PPHASH(self, t):
        r'[ \t]*\#'
        if self.line_pattern.match(t.lexer.lexdata, pos=t.lexer.lexpos):
            t.lexer.begin('ppline')
            self.pp_line = self.pp_filename = None
        elif self.pragma_pattern.match(t.lexer.lexdata, pos=t.lexer.lexpos):
            t.lexer.begin('pppragma')
        else:
            t.type = 'PPHASH'
            return t

    ##
    ## Rules for the ppline state
    ##
    @TOKEN(string_literal)
    def t_ppline_FILENAME(self, t):
        if self.pp_line is None:
            self._error('filename before line number in #line', t)
        else:
            self.pp_filename = t.value.lstrip('"').rstrip('"')

    @TOKEN(decimal_constant)
    def t_ppline_LINE_NUMBER(self, t):
        if self.pp_line is None:
            self.pp_line = t.value
        else:
            # Ignore: GCC's cpp sometimes inserts a numeric flag
            # after the file name
            pass

    def t_ppline_NEWLINE(self, t):
        r'\n'

        if self.pp_line is None:
            self._error('line number missing in #line', t)
        else:
            self.lexer.lineno = int(self.pp_line)

            if self.pp_filename is not None:
                self.filename = self.pp_filename

        t.lexer.begin('INITIAL')

    def t_ppline_PPLINE(self, t):
        r'line'
        pass

    t_ppline_ignore = ' \t'

    def t_ppline_error(self, t):
        self._error('invalid #line directive', t)

    ##
    ## Rules for the pppragma state
    ##
    def t_pppragma_NEWLINE(self, t):
        r'\n'
        t.lexer.lineno += 1
        t.lexer.begin('INITIAL')

    def t_pppragma_PPPRAGMA(self, t):
        r'pragma'
        pass

    t_pppragma_ignore = ' \t<>.-{}();+-*/$%@&^~!?:,0123456789'

    @TOKEN(string_literal)
    def t_pppragma_STR(self, t): pass

    @TOKEN(identifier)
    def t_pppragma_ID(self, t): pass

    def t_pppragma_error(self, t):
        self._error('invalid #pragma directive', t)

    ##
    ## Rules for the normal state
    ##
    t_ignore = ' \t'

    # Newlines
    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count("\n")

    # Operators
    t_PLUS              = r'\+'
    t_MINUS             = r'-'
    t_TIMES             = r'\*'
    t_DIVIDE            = r'/'
    t_MOD               = r'%'
    t_OR                = r'\|'
    t_AND               = r'&'
    t_NOT               = r'~'
    t_XOR               = r'\^'
    t_LSHIFT            = r'<<'
    t_RSHIFT            = r'>>'
    t_LOR               = r'\|\|'
    t_LAND              = r'&&'
    t_LNOT              = r'!'
    t_LT                = r'<'
    t_GT                = r'>'
    t_LE                = r'<='
    t_GE                = r'>='
    t_EQ                = r'=='
    t_NE                = r'!='

    # Assignment operators
    t_EQUALS            = r'='
    t_TIMESEQUAL        = r'\*='
    t_DIVEQUAL          = r'/='
    t_MODEQUAL          = r'%='
    t_PLUSEQUAL         = r'\+='
    t_MINUSEQUAL        = r'-='
    t_LSHIFTEQUAL       = r'<<='
    t_RSHIFTEQUAL       = r'>>='
    t_ANDEQUAL          = r'&='
    t_OREQUAL           = r'\|='
    t_XOREQUAL          = r'\^='

    # Increment/decrement
    t_PLUSPLUS          = r'\+\+'
    t_MINUSMINUS        = r'--'

    # ->
    t_ARROW             = r'->'

    # ?
    t_CONDOP            = r'\?'

    # Delimeters
    t_LPAREN            = r'\('
    t_RPAREN            = r'\)'
    t_LBRACKET          = r'\['
    t_RBRACKET          = r'\]'
    t_COMMA             = r','
    t_PERIOD            = r'\.'
    t_SEMI              = r';'
    t_COLON             = r':'
    t_ELLIPSIS          = r'\.\.\.'

    # Scope delimiters
    # To see why on_lbrace_func is needed, consider:
    #   typedef char TT;
    #   void foo(int TT) { TT = 10; }
    #   TT x = 5;
    # Outside the function, TT is a typedef, but inside (starting and ending
    # with the braces) it's a parameter.  The trouble begins with yacc's
    # lookahead token.  If we open a new scope in brace_open, then TT has
    # already been read and incorrectly interpreted as TYPEID.  So, we need
    # to open and close scopes from within the lexer.
    # Similar for the TT immediately outside the end of the function.
    #
    @TOKEN(r'\{')
    def t_LBRACE(self, t):
        self.on_lbrace_func()
        return t
    @TOKEN(r'\}')
    def t_RBRACE(self, t):
        self.on_rbrace_func()
        return t

    t_STRING_LITERAL = string_literal

    # The following floating and integer constants are defined as
    # functions to impose a strict order (otherwise, decimal
    # is placed before the others because its regex is longer,
    # and this is bad)
    #
    @TOKEN(floating_constant)
    def t_FLOAT_CONST(self, t):
        return t

    @TOKEN(hex_floating_constant)
    def t_HEX_FLOAT_CONST(self, t):
        return t

    @TOKEN(hex_constant)
    def t_INT_CONST_HEX(self, t):
        return t

    @TOKEN(bad_octal_constant)
    def t_BAD_CONST_OCT(self, t):
        msg = "Invalid octal constant"
        self._error(msg, t)

    @TOKEN(octal_constant)
    def t_INT_CONST_OCT(self, t):
        return t

    @TOKEN(decimal_constant)
    def t_INT_CONST_DEC(self, t):
        return t

    # Must come before bad_char_const, to prevent it from
    # catching valid char constants as invalid
    #
    @TOKEN(char_const)
    def t_CHAR_CONST(self, t):
        return t

    @TOKEN(wchar_const)
    def t_WCHAR_CONST(self, t):
        return t

    @TOKEN(unmatched_quote)
    def t_UNMATCHED_QUOTE(self, t):
        msg = "Unmatched '"
        self._error(msg, t)

    @TOKEN(bad_char_const)
    def t_BAD_CHAR_CONST(self, t):
        msg = "Invalid char constant %s" % t.value
        self._error(msg, t)

    @TOKEN(wstring_literal)
    def t_WSTRING_LITERAL(self, t):
        return t

    # unmatched string literals are caught by the preprocessor

    @TOKEN(bad_string_literal)
    def t_BAD_STRING_LITERAL(self, t):
        msg = "String contains invalid escape code"
        self._error(msg, t)

    @TOKEN(identifier)
    def t_ID(self, t):
        t.type = self.keyword_map.get(t.value, "ID")
        if t.type == 'ID' and self.type_lookup_func(t.value):
            t.type = "TYPEID"
        return t

    def t_error(self, t):
        msg = 'Illegal character %s' % repr(t.value[0])
        self._error(msg, t)

