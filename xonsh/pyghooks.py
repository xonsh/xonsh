"""Hooks for pygments syntax highlighting."""
from __future__ import print_function, unicode_literals

from pygments.lexer import DelegatingLexer
from pygments.lexers.shell import BashLexer
from pygments.lexers.agile import PythonLexer, PythonConsoleLexer


class XonshLexer(DelegatingLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh lexer'
    aliases = ['xonsh', 'xsh']
    filenames = ['*.xsh', '*xonshrc']

    def __init__(self, **options):
        super(XonshLexer, self).__init__(BashLexer, PythonLexer, **options)


class XonshConsoleLexer(DelegatingLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh console lexer'
    aliases = ['xonshcon']

    def __init__(self, **options):
        super(XonshConsoleLexer, self).__init__(BashLexer, PythonConsoleLexer,
                                                **options)
