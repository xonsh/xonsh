"""Hooks for pygments syntax highlighting."""
from __future__ import print_function, unicode_literals
import re

from pygments.lexer import RegexLexer, inherit, bygroups, using, DelegatingLexer
from pygments.token import Punctuation, Name, Generic, Keyword, Text
from pygments.lexers.shell import BashLexer
from pygments.lexers.agile import PythonLexer, PythonConsoleLexer


class XonshLexer(DelegatingLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh lexer'
    aliases = ['xonsh', 'xsh']
    filenames = ['*.xsh', '*xonshrc']

    def __init__(self, **options):
        super(XonshLexer, self).__init__(BashLexer, PythonLexer, **options)


#class XonshConsoleLexer(PythonConsoleLexer):
class XonshConsoleLexer(PythonLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh console lexer'
    aliases = ['xonshcon']

    flags = re.DOTALL

    tokens = {
        'root': [
            (r'^(>>>|\.\.\.) ', Generic.Prompt),
            (r'\n(>>>|\.\.\.) ', Generic.Prompt),
            #(r'(?![>.][>.][>.] )(.*)', bygroups(Generic.Output)),
            (r'\n(?![>.][>.][>.] )([^\n]*)', Generic.Output),
            (r'\n(?![>.][>.][>.] )(.*?)$', Generic.Output),
            (r'\$\(', Keyword, ('subproc',)),
            inherit,
            ],
        'subproc': [
            (r'(.+?)(\))', bygroups(using(BashLexer), Keyword), '#pop'),
            ],
        }