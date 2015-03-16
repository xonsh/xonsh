"""A lexer and parser for the troff format, which is used in man pages."""
from __future__ import print_function, unicode_literals
import re
import sys

from ply import lex
from ply.lex import TOKEN


class TroffLexer(object):
    """A lexer for troff."""

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
        self.reset()

    def reset(self):
        self.lexer.lineno = 1
        self.last = None

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
    # All the tokens recognized by the lexer
    #
    tokens = (
        # Delimeters
        'NEWLINE', 'COMMENT', 'ENDMARKER', 'SPACE',

        # Macros
        'TITLE', 'SECTION', 'SUBSECTION', 'PARAGRAPH', 'HANGING_PARAGRAPH',
        'INDENT_START', 'INDENT_END',

        # Text and font
        'WORD', 'ITALICS', 'BOLD'
        )

    #
    # Rules 
    #

    # Newlines
    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
        return t

    # Delimeters
    t_COMMENT = r'^\.\\".*$'
    t_ENDMARKER = r'\x03'
    t_SPACE = r'[ ]+'

    # Macros
    t_TITLE = r'^\.TH'
    t_SECTION = r'^\.SH'
    t_SUBSECTION = r'^\.SS'
    t_PARAGRAPH = r'^\.P'
    t_HANGING_PARAGRAPH = r'^\.HP'
    t_INDENT_START = r'^\.RS'
    t_INDENT_END = r'^\.RE'

    # Text
    t_WORD = r'^[^.][^ ]+'
    t_ITALICS = r'^\.I'
    t_BOLD = r'^\.B'

    def t_error(self, t):
        msg = 'Invalid token {0!r}'.format(t.value[0])
        self._error(msg, t)

