"""Hooks for pygments syntax highlighting."""
from pygments.lexer import inherit, bygroups, using, this
from pygments.token import Name, Generic, Keyword, Text, String
from pygments.lexers.shell import BashLexer
from pygments.lexers.agile import PythonLexer


class XonshSubprocLexer(BashLexer):
    """Lexer for xonsh subproc mode."""

    name = 'Xonsh subprocess lexer'

    tokens = {'root': [(r'`[^`]*?`', String.Backtick), inherit, ]}


ROOT_TOKENS = [(r'\?', Keyword),
               (r'\$\w+', Name.Variable),
               (r'\$\{', Keyword, ('pymode', )),
               (r'\$\(', Keyword, ('subproc', )),
               (r'\$\[', Keyword, ('subproc', )),
               (r'@\(', Keyword, ('pymode', )),
               inherit, ]

PYMODE_TOKENS = [(r'(.+)(\))', bygroups(using(this), Keyword), '#pop'),
                 (r'(.+)(\})', bygroups(using(this), Keyword), '#pop'), ]

SUBPROC_TOKENS = [
    (r'(.+)(\))', bygroups(using(XonshSubprocLexer), Keyword), '#pop'),
    (r'(.+)(\])', bygroups(using(XonshSubprocLexer), Keyword), '#pop'),
]


class XonshLexer(PythonLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh lexer'
    aliases = ['xonsh', 'xsh']
    filenames = ['*.xsh', '*xonshrc']

    tokens = {
        'root': list(ROOT_TOKENS),
        'pymode': PYMODE_TOKENS,
        'subproc': SUBPROC_TOKENS,
    }


class XonshConsoleLexer(PythonLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh console lexer'
    aliases = ['xonshcon']
    filenames = []

    tokens = {
        'root': [(r'^(>>>|\.\.\.) ', Generic.Prompt),
                 (r'\n(>>>|\.\.\.)', Generic.Prompt),
                 (r'\n(?![>.][>.][>.] )([^\n]*)', Generic.Output),
                 (r'\n(?![>.][>.][>.] )(.*?)$', Generic.Output)] + ROOT_TOKENS,
        'pymode': PYMODE_TOKENS,
        'subproc': SUBPROC_TOKENS,
    }

# XonshLexer & XonshSubprocLexer have to refernce each other
XonshSubprocLexer.tokens['root'] = [
    (r'(\$\{)(.*)(\})', bygroups(Keyword, using(XonshLexer), Keyword)),
    (r'(@\()(.+)(\))', bygroups(Keyword, using(XonshLexer), Keyword)),
] + XonshSubprocLexer.tokens['root']
