# -*- coding: utf-8 -*-
"""Hooks for pygments syntax highlighting."""
import os
import re
import sys
import string
import builtins
from collections import ChainMap
from collections.abc import MutableMapping

# must come before pygments imports
from xonsh.lazyasd import load_module_in_background

from pygments.lexer import inherit, bygroups, include
from pygments.lexers.agile import PythonLexer
from pygments.token import (Keyword, Name, Comment, String, Error, Number,
                            Operator, Generic, Whitespace, Token, Punctuation,
                            Text)
from pygments.style import Style
from pygments.styles import get_style_by_name
import pygments.util

from xonsh.commands_cache import CommandsCache
from xonsh.lazyasd import LazyObject, LazyDict, lazyobject
from xonsh.tools import (ON_WINDOWS, intensify_colors_for_cmd_exe,
                         expand_gray_colors_for_cmd_exe)
from xonsh.color_tools import (RE_BACKGROUND, BASE_XONSH_COLORS, make_pallete,
                               find_closest_color)
from xonsh.style_tools import norm_name
from xonsh.lazyimps import terminal256
from xonsh.platform import os_environ

load_module_in_background('pkg_resources', debug='XONSH_DEBUG',
                          replacements={'pygments.plugin': 'pkg_resources'})


def _command_is_valid(cmd):
    try:
        cmd_abspath = os.path.abspath(os.path.expanduser(cmd))
    except (FileNotFoundError, OSError):
        return False
    return cmd in builtins.__xonsh_commands_cache__ or \
        (os.path.isfile(cmd_abspath) and os.access(cmd_abspath, os.X_OK))


def _command_is_autocd(cmd):
    if not builtins.__xonsh_env__.get('AUTO_CD', False):
        return False
    try:
        cmd_abspath = os.path.abspath(os.path.expanduser(cmd))
    except (FileNotFoundError, OSError):
        return False
    return os.path.isdir(cmd_abspath)


def subproc_cmd_callback(_, match):
    """Yield Builtin token if match contains valid command,
    otherwise fallback to fallback lexer.
    """
    cmd = match.group()
    yield match.start(), Name.Builtin if _command_is_valid(cmd) else Error, cmd


def subproc_arg_callback(_, match):
    """Check if match contains valid path"""
    text = match.group()
    try:
        ispath = os.path.exists(os.path.expanduser(text))
    except (FileNotFoundError, OSError):
        ispath = False
    yield (match.start(), Name.Constant if ispath else Text, text)


COMMAND_TOKEN_RE = r'[^=\s\[\]{}()$"\'`<&|;!]+(?=\s|$|\)|\]|\}|!)'


class XonshLexer(PythonLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh lexer'
    aliases = ['xonsh', 'xsh']
    filenames = ['*.xsh', '*xonshrc']

    def __init__(self, *args, **kwargs):
        # If the lexor is loaded as a pygment plugin, we have to mock
        # __xonsh_env__ and __xonsh_commands_cache__
        if not hasattr(builtins, '__xonsh_env__'):
            setattr(builtins, '__xonsh_env__', {})
            if ON_WINDOWS:
                pathext = os_environ.get('PATHEXT', ['.EXE', '.BAT', '.CMD'])
                builtins.__xonsh_env__['PATHEXT'] = pathext.split(os.pathsep)
        if not hasattr(builtins, '__xonsh_commands_cache__'):
            setattr(builtins, '__xonsh_commands_cache__', CommandsCache())
        _ = builtins.__xonsh_commands_cache__.all_commands  # NOQA
        super().__init__(*args, **kwargs)

    tokens = {
        'mode_switch_brackets': [
            (r'(\$)(\{)', bygroups(Keyword, Punctuation), 'py_curly_bracket'),
            (r'(@)(\()', bygroups(Keyword, Punctuation), 'py_bracket'),
            (r'([\!\$])(\()', bygroups(Keyword, Punctuation),
             ('subproc_bracket', 'subproc_start')),
            (r'(@\$)(\()', bygroups(Keyword, Punctuation),
             ('subproc_bracket', 'subproc_start')),
            (r'([\!\$])(\[)', bygroups(Keyword, Punctuation),
             ('subproc_square_bracket', 'subproc_start')),
            (r'(g?)(`)', bygroups(String.Affix, String.Backtick),
             'backtick_re'),
        ],
        'subproc_bracket': [
            (r'\)', Punctuation, '#pop'),
            include('subproc'),
        ],
        'subproc_square_bracket': [
            (r'\]', Punctuation, '#pop'),
            include('subproc'),
        ],
        'py_bracket': [
            (r'\)', Punctuation, '#pop'),
            include('root'),
        ],
        'py_curly_bracket': [
            (r'\}', Punctuation, '#pop'),
            include('root'),
        ],
        'backtick_re': [
            (r'[\.\^\$\*\+\?\[\]\|]', String.Regex),
            (r'({[0-9]+}|{[0-9]+,[0-9]+})\??', String.Regex),
            (r'\\([0-9]+|[AbBdDsSwWZabfnrtuUvx\\])', String.Escape),
            (r'`', String.Backtick, '#pop'),
            (r'[^`\.\^\$\*\+\?\[\]\|]+', String.Backtick),
        ],
        'root': [
            (r'\?', Keyword),
            (r'(?<=\w)!', Keyword),
            (r'\$\w+', Name.Variable),
            (r'\(', Punctuation, 'py_bracket'),
            (r'\{', Punctuation, 'py_curly_bracket'),
            include('mode_switch_brackets'),
            inherit,
        ],
        'subproc_start': [
            (r'\s+', Whitespace),
            (COMMAND_TOKEN_RE, subproc_cmd_callback, '#pop'),
            (r'', Whitespace, '#pop'),
        ],
        'subproc': [
            include('mode_switch_brackets'),
            (r'&&|\|\|', Operator, 'subproc_start'),
            (r'"(\\\\|\\[0-7]+|\\.|[^"\\])*"', String.Double),
            (r"'(\\\\|\\[0-7]+|\\.|[^'\\])*'", String.Single),
            (r'(?<=\w|\s)!', Keyword, 'subproc_macro'),
            (r'^!', Keyword, 'subproc_macro'),
            (r';', Punctuation, 'subproc_start'),
            (r'&|=', Punctuation),
            (r'\|', Punctuation, 'subproc_start'),
            (r'\s+', Text),
            (r'[^=\s\[\]{}()$"\'`<&|;]+', subproc_arg_callback),
            (r'<', Text),
            (r'\$\w+', Name.Variable),
        ],
        'subproc_macro': [
            (r'(\s*)([^\n]+)', bygroups(Whitespace, String)),
            (r'', Whitespace, '#pop'),
        ],
    }

    def get_tokens_unprocessed(self, text):
        """Check first command, then call super.get_tokens_unprocessed
        with root or subproc state"""
        start = 0
        state = ('root', )
        m = re.match(r'(\s*)({})'.format(COMMAND_TOKEN_RE), text)
        if m is not None:
            yield m.start(1), Whitespace, m.group(1)
            cmd = m.group(2)
            cmd_is_valid = _command_is_valid(cmd)
            cmd_is_autocd = _command_is_autocd(cmd)

            if cmd_is_valid or cmd_is_autocd:
                yield (m.start(2),
                       Name.Builtin if cmd_is_valid else Name.Constant,
                       cmd)
                start = m.end(2)
                state = ('subproc', )

        for i, t, v in super().get_tokens_unprocessed(text[start:], state):
            yield i + start, t, v


class XonshConsoleLexer(XonshLexer):
    """Xonsh console lexer for pygments."""

    name = 'Xonsh console lexer'
    aliases = ['xonshcon']
    filenames = []

    tokens = {
        'root': [(r'^(>>>|\.\.\.) ', Generic.Prompt),
                 (r'\n(>>>|\.\.\.)', Generic.Prompt),
                 (r'\n(?![>.][>.][>.] )([^\n]*)', Generic.Output),
                 (r'\n(?![>.][>.][>.] )(.*?)$', Generic.Output),
                 inherit]
    }


#
# Colors and Styles
#

Color = Token.Color  # alias to new color token namespace


def color_by_name(name, fg=None, bg=None):
    """Converts a color name to a color token, foreground name,
    and background name.  Will take into consideration current foreground
    and background colors, if provided.

    Parameters
    ----------
    name : str
        Color name.
    fg : str, optional
        Foreground color name.
    bg : str, optional
        Background color name.

    Returns
    -------
    tok : Token
        Pygments Token.Color subclass
    fg : str or None
        New computed foreground color name.
    bg : str or None
        New computed background color name.
    """
    name = name.upper()
    if name == 'NO_COLOR':
        return Color.NO_COLOR, None, None
    m = RE_BACKGROUND.search(name)
    if m is None:  # must be foreground color
        fg = norm_name(name)
    else:
        bg = norm_name(name)
    # assmble token
    if fg is None and bg is None:
        tokname = 'NO_COLOR'
    elif fg is None:
        tokname = bg
    elif bg is None:
        tokname = fg
    else:
        tokname = fg + '__' + bg
    tok = getattr(Color, tokname)
    return tok, fg, bg


def code_by_name(name, styles):
    """Converts a token name into a pygments-style color code.

    Parameters
    ----------
    name : str
        Color token name.
    styles : Mapping
        Mapping for looking up non-hex colors

    Returns
    -------
    code : str
        Pygments style color code.
    """
    fg, _, bg = name.lower().partition('__')
    if fg.startswith('background_'):
        fg, bg = bg, fg
    codes = []
    # foreground color
    if len(fg) == 0:
        pass
    elif 'hex' in fg:
        for p in fg.split('_'):
            codes.append('#'+p[3:] if p.startswith('hex') else p)
    else:
        fgtok = getattr(Color, fg.upper())
        if fgtok in styles:
            codes.append(styles[fgtok])
        else:
            codes += fg.split('_')
    # background color
    if len(bg) == 0:
        pass
    elif bg.startswith('background_hex'):
        codes.append('bg:#'+bg[14:])
    else:
        bgtok = getattr(Color, bg.upper())
        if bgtok in styles:
            codes.append(styles[bgtok])
        else:
            codes.append(bg.replace('background_', 'bg:'))
    code = ' '.join(codes)
    return code


def partial_color_tokenize(template):
    """Tokenizes a template string containing colors. Will return a list
    of tuples mapping the token to the string which has that color.
    These sub-strings maybe templates themselves.
    """
    if hasattr(builtins, '__xonsh_shell__'):
        styles = __xonsh_shell__.shell.styler.styles
    else:
        styles = None
    color = Color.NO_COLOR
    try:
        toks, color = _partial_color_tokenize_main(template, styles)
    except Exception:
        toks = [(Color.NO_COLOR, template)]
    if styles is not None:
        styles[color]  # ensure color is available
    return toks


def _partial_color_tokenize_main(template, styles):
    formatter = string.Formatter()
    bopen = '{'
    bclose = '}'
    colon = ':'
    expl = '!'
    color = Color.NO_COLOR
    fg = bg = None
    value = ''
    toks = []
    for literal, field, spec, conv in formatter.parse(template):
        if field is None:
            value += literal
        elif field in KNOWN_COLORS or '#' in field:
            value += literal
            next_color, fg, bg = color_by_name(field, fg, bg)
            if next_color is not color:
                if len(value) > 0:
                    toks.append((color, value))
                    if styles is not None:
                        styles[color]  # ensure color is available
                color = next_color
                value = ''
        elif field is not None:
            parts = [literal, bopen, field]
            if conv is not None and len(conv) > 0:
                parts.append(expl)
                parts.append(conv)
            if spec is not None and len(spec) > 0:
                parts.append(colon)
                parts.append(spec)
            parts.append(bclose)
            value += ''.join(parts)
        else:
            value += literal
    toks.append((color, value))
    return toks, color


class CompoundColorMap(MutableMapping):
    """Looks up color tokes by name, potentailly generating the value
    from the lookup.
    """

    def __init__(self, styles, *args, **kwargs):
        self.styles = styles
        self.colors = dict(*args, **kwargs)

    def __getitem__(self, key):
        if key in self.colors:
            return self.colors[key]
        if key in self.styles:
            value = self.styles[key]
            self[key] = value
            return value
        if key is Color:
            raise KeyError
        pre, _, name = str(key).rpartition('.')
        if pre != 'Token.Color':
            raise KeyError
        value = code_by_name(name, self.styles)
        self[key] = value
        return value

    def __setitem__(self, key, value):
        self.colors[key] = value

    def __delitem__(self, key):
        del self.colors[key]

    def __iter__(self):
        yield from self.colors.keys()

    def __len__(self):
        return len(self.colors)


class XonshStyle(Style):
    """A xonsh pygments style that will dispatch to the correct color map
    by using a ChainMap.  The style_name property may be used to reset
    the current style.
    """

    def __init__(self, style_name='default'):
        """
        Parameters
        ----------
        style_name : str, optional
            The style name to initialize with.
        """
        self.trap = {}  # for traping custom colors set by user
        self._smap = {}
        self._style_name = ''
        self.style_name = style_name
        super().__init__()

    @property
    def style_name(self):
        return self._style_name

    @style_name.setter
    def style_name(self, value):
        if self._style_name == value:
            return
        if value not in STYLES:
            try:  # loading style dynamically
                pygments_style_by_name(value)
            except Exception:
                print('Could not find style {0!r}, using default'.format(value),
                      file=sys.stderr)
                value = 'default'
                builtins.__xonsh_env__['XONSH_COLOR_STYLE'] = value
        cmap = STYLES[value]
        if value == 'default':
            self._smap = XONSH_BASE_STYLE.copy()
        else:
            try:
                self._smap = get_style_by_name(value)().styles.copy()
            except (ImportError, pygments.util.ClassNotFound):
                self._smap = XONSH_BASE_STYLE.copy()
        compound = CompoundColorMap(ChainMap(self.trap, cmap, PTK_STYLE, self._smap))
        self.styles = ChainMap(self.trap, cmap, PTK_STYLE, self._smap, compound)
        self._style_name = value
        if ON_WINDOWS:
            self.enhance_colors_for_cmd_exe()

    @style_name.deleter
    def style_name(self):
        self._style_name = ''

    def enhance_colors_for_cmd_exe(self):
        """ Enhance colors when using cmd.exe on windows.
            When using the default style all blue and dark red colors
            are changed to CYAN and intence red.
        """
        env = builtins.__xonsh_env__
        # Ensure we are not using ConEmu
        if 'CONEMUANSI' not in env:
            if not hasattr(pygments.style, 'ansicolors'):
                # Auto suggest needs to be a darker shade to be distinguishable
                # from the default color
                self.styles[Token.AutoSuggestion] = '#444444'
                self._smap.update(expand_gray_colors_for_cmd_exe(self._smap))
            if env.get('INTENSIFY_COLORS_ON_WIN', False):
                has_ansi = hasattr(pygments.style, 'ansicolors')
                newcolors = intensify_colors_for_cmd_exe(self._smap, ansi=has_ansi)
                self._smap.update(newcolors)


def xonsh_style_proxy(styler):
    """Factory for a proxy class to a xonsh style."""
    class XonshStyleProxy(Style):
        """Simple proxy class to fool prompt toolkit."""

        target = styler
        styles = styler.styles

        def __new__(cls, *args, **kwargs):
            return cls.target

    return XonshStyleProxy


if hasattr(pygments.style, 'ansicolors'):
    PTK_STYLE = {
        Token.Menu.Completions: 'bg:#ansilightgray #ansiblack',
        Token.Menu.Completions.Completion: '',
        Token.Menu.Completions.Completion.Current: 'bg:#ansidarkgray #ansiwhite',
        Token.Scrollbar: 'bg:#ansidarkgray',
        Token.Scrollbar.Button: 'bg:#ansiblack',
        Token.Scrollbar.Arrow: 'bg:#ansiblack #ansiwhite bold',
        Token.AutoSuggestion: '#ansidarkgray',
        Token.Aborted: '#ansidarkgray',
    }
else:
    PTK_STYLE = {
        Token.Menu.Completions: 'bg:#888888 #000000',
        Token.Menu.Completions.Completion: '',
        Token.Menu.Completions.Completion.Current: 'bg:#555555 #ffffff',
        Token.Scrollbar: 'bg:#555555',
        Token.Scrollbar.Button: 'bg:#000000',
        Token.Scrollbar.Arrow: 'bg:#000000 #ffffff bold',
        Token.AutoSuggestion: '#666666',
        Token.Aborted: '#666666',
    }

if hasattr(pygments.style, 'ansicolors'):
    XONSH_BASE_STYLE = LazyObject(lambda: {
        Whitespace: '#ansilightgray',
        Comment: 'underline #ansiteal',
        Comment.Preproc: 'underline #ansibrown',
        Keyword: 'bold #ansidarkgreen',
        Keyword.Pseudo: 'nobold',
        Keyword.Type: 'nobold #ansidarkred',
        Operator: '#ansidarkgray',
        Operator.Word: 'bold #ansipurple',
        Name.Builtin: '#ansidarkgreen',
        Name.Function: '#ansiblue',
        Name.Class: 'bold #ansiblue',
        Name.Namespace: 'bold #ansiblue',
        Name.Exception: 'bold #ansired',
        Name.Variable: '#ansidarkblue',
        Name.Constant: '#ansidarkred',
        Name.Label: '#ansiyellow',
        Name.Entity: 'bold #ansilightgray',
        Name.Attribute: '#ansiyellow',
        Name.Tag: 'bold #ansidarkgreen',
        Name.Decorator: '#ansifuchsia',
        String: '#ansired',
        String.Doc: 'underline',
        String.Interpol: 'bold #ansipurple',
        String.Escape: 'bold #ansibrown',
        String.Regex: '#ansipurple',
        String.Symbol: '#ansibrown',
        String.Other: '#ansidarkgreen',
        Number: '#ansidarkgray',
        Generic.Heading: 'bold #ansidarkblue',
        Generic.Subheading: 'bold #ansipurple',
        Generic.Deleted: '#ansidarkred',
        Generic.Inserted: '#ansigreen',
        Generic.Error: 'bold #ansired',
        Generic.Emph: 'underline',
        Generic.Prompt: 'bold #ansidarkblue',
        Generic.Output: '#ansidarkblue',
        Generic.Traceback: '#ansidarkblue',
        Error: '#ansired',
        }, globals(), 'XONSH_BASE_STYLE')
else:
    XONSH_BASE_STYLE = LazyObject(lambda: {
        Whitespace: "#bbbbbb",
        Comment: "italic #408080",
        Comment.Preproc: "noitalic #BC7A00",
        Keyword: "bold #008000",
        Keyword.Pseudo: "nobold",
        Keyword.Type:   "nobold #B00040",
        Operator:   "#666666",
        Operator.Word:  "bold #AA22FF",
        Name.Builtin: "#008000",
        Name.Function: "#0000FF",
        Name.Class: "bold #0000FF",
        Name.Namespace: "bold #0000FF",
        Name.Exception: "bold #D2413A",
        Name.Variable: "#19177C",
        Name.Constant: "#880000",
        Name.Label: "#A0A000",
        Name.Entity: "bold #999999",
        Name.Attribute: "#7D9029",
        Name.Tag: "bold #008000",
        Name.Decorator: "#AA22FF",
        String: "#BA2121",
        String.Doc: "italic",
        String.Interpol: "bold #BB6688",
        String.Escape: "bold #BB6622",
        String.Regex: "#BB6688",
        String.Symbol: "#19177C",
        String.Other: "#008000",
        Number: "#666666",
        Generic.Heading: "bold #000080",
        Generic.Subheading: "bold #800080",
        Generic.Deleted: "#A00000",
        Generic.Inserted: "#00A000",
        Generic.Error: "#FF0000",
        Generic.Emph: "italic",
        Generic.Strong: "bold",
        Generic.Prompt: "bold #000080",
        Generic.Output: "#888",
        Generic.Traceback: "#04D",
        Error: "border:#FF0000"
    }, globals(), 'XONSH_BASE_STYLE')


KNOWN_COLORS = LazyObject(lambda: frozenset([
    'BACKGROUND_BLACK',
    'BACKGROUND_BLUE',
    'BACKGROUND_CYAN',
    'BACKGROUND_GREEN',
    'BACKGROUND_INTENSE_BLACK',
    'BACKGROUND_INTENSE_BLUE',
    'BACKGROUND_INTENSE_CYAN',
    'BACKGROUND_INTENSE_GREEN',
    'BACKGROUND_INTENSE_PURPLE',
    'BACKGROUND_INTENSE_RED',
    'BACKGROUND_INTENSE_WHITE',
    'BACKGROUND_INTENSE_YELLOW',
    'BACKGROUND_PURPLE',
    'BACKGROUND_RED',
    'BACKGROUND_WHITE',
    'BACKGROUND_YELLOW',
    'BLACK',
    'BLUE',
    'BOLD_BLACK',
    'BOLD_BLUE',
    'BOLD_CYAN',
    'BOLD_GREEN',
    'BOLD_INTENSE_BLACK',
    'BOLD_INTENSE_BLUE',
    'BOLD_INTENSE_CYAN',
    'BOLD_INTENSE_GREEN',
    'BOLD_INTENSE_PURPLE',
    'BOLD_INTENSE_RED',
    'BOLD_INTENSE_WHITE',
    'BOLD_INTENSE_YELLOW',
    'BOLD_PURPLE',
    'BOLD_RED',
    'BOLD_UNDERLINE_BLACK',
    'BOLD_UNDERLINE_BLUE',
    'BOLD_UNDERLINE_CYAN',
    'BOLD_UNDERLINE_GREEN',
    'BOLD_UNDERLINE_INTENSE_BLACK',
    'BOLD_UNDERLINE_INTENSE_BLUE',
    'BOLD_UNDERLINE_INTENSE_CYAN',
    'BOLD_UNDERLINE_INTENSE_GREEN',
    'BOLD_UNDERLINE_INTENSE_PURPLE',
    'BOLD_UNDERLINE_INTENSE_RED',
    'BOLD_UNDERLINE_INTENSE_WHITE',
    'BOLD_UNDERLINE_INTENSE_YELLOW',
    'BOLD_UNDERLINE_PURPLE',
    'BOLD_UNDERLINE_RED',
    'BOLD_UNDERLINE_WHITE',
    'BOLD_UNDERLINE_YELLOW',
    'BOLD_WHITE',
    'BOLD_YELLOW',
    'CYAN',
    'GREEN',
    'INTENSE_BLACK',
    'INTENSE_BLUE',
    'INTENSE_CYAN',
    'INTENSE_GREEN',
    'INTENSE_PURPLE',
    'INTENSE_RED',
    'INTENSE_WHITE',
    'INTENSE_YELLOW',
    'NO_COLOR',
    'PURPLE',
    'RED',
    'UNDERLINE_BLACK',
    'UNDERLINE_BLUE',
    'UNDERLINE_CYAN',
    'UNDERLINE_GREEN',
    'UNDERLINE_INTENSE_BLACK',
    'UNDERLINE_INTENSE_BLUE',
    'UNDERLINE_INTENSE_CYAN',
    'UNDERLINE_INTENSE_GREEN',
    'UNDERLINE_INTENSE_PURPLE',
    'UNDERLINE_INTENSE_RED',
    'UNDERLINE_INTENSE_WHITE',
    'UNDERLINE_INTENSE_YELLOW',
    'UNDERLINE_PURPLE',
    'UNDERLINE_RED',
    'UNDERLINE_WHITE',
    'UNDERLINE_YELLOW',
    'WHITE',
    'YELLOW',
    ]), globals(), 'KNOWN_COLORS')


def _expand_style(cmap):
    """Expands a style in order to more quickly make color map changes."""
    for key, val in list(cmap.items()):
        if key is Color.NO_COLOR:
            continue
        _, _, key = str(key).rpartition('.')
        cmap[getattr(Color, 'BOLD_'+key)] = 'bold ' + val
        cmap[getattr(Color, 'UNDERLINE_'+key)] = 'underline ' + val
        cmap[getattr(Color, 'BOLD_UNDERLINE_'+key)] = 'bold underline ' + val
        if val == 'noinherit':
            cmap[getattr(Color, 'BACKGROUND_'+key)] = val
        else:
            cmap[getattr(Color, 'BACKGROUND_'+key)] = 'bg:' + val


def _bw_style():
    style = {
        Color.BLACK: 'noinherit',
        Color.BLUE: 'noinherit',
        Color.CYAN: 'noinherit',
        Color.GREEN: 'noinherit',
        Color.INTENSE_BLACK: 'noinherit',
        Color.INTENSE_BLUE: 'noinherit',
        Color.INTENSE_CYAN: 'noinherit',
        Color.INTENSE_GREEN: 'noinherit',
        Color.INTENSE_PURPLE: 'noinherit',
        Color.INTENSE_RED: 'noinherit',
        Color.INTENSE_WHITE: 'noinherit',
        Color.INTENSE_YELLOW: 'noinherit',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: 'noinherit',
        Color.RED: 'noinherit',
        Color.WHITE: 'noinherit',
        Color.YELLOW: 'noinherit',
        }
    _expand_style(style)
    return style


def _default_style():
    if hasattr(pygments.style, 'ansicolors'):
        style = {
            Color.BLACK: '#ansiblack',
            Color.BLUE: '#ansidarkblue',
            Color.CYAN: '#ansiteal',
            Color.GREEN: '#ansidarkgreen',
            Color.INTENSE_BLACK: '#ansidarkgray',
            Color.INTENSE_BLUE: '#ansiblue',
            Color.INTENSE_CYAN: '#ansiturquoise',
            Color.INTENSE_GREEN: '#ansigreen',
            Color.INTENSE_PURPLE: '#ansifuchsia',
            Color.INTENSE_RED: '#ansired',
            Color.INTENSE_WHITE: '#ansiwhite',
            Color.INTENSE_YELLOW: '#ansiyellow',
            Color.NO_COLOR: 'noinherit',
            Color.PURPLE: '#ansipurple',
            Color.RED: '#ansidarkred',
            Color.WHITE: '#ansilightgray',
            Color.YELLOW: '#ansibrown',
        }
    elif ON_WINDOWS and 'CONEMUANSI' not in os_environ:
        # These colors must match the color specification
        # in prompt_toolkit, so the colors are converted
        # correctly when using cmd.exe
        style = {
            Color.BLACK: '#000000',
            Color.BLUE: '#0000AA',
            Color.CYAN: '#00AAAA',
            Color.GREEN: '#00AA00',
            Color.INTENSE_BLACK: '#444444',
            Color.INTENSE_BLUE: '#4444FF',
            Color.INTENSE_CYAN: '#44FFFF',
            Color.INTENSE_GREEN: '#44FF44',
            Color.INTENSE_PURPLE: '#FF44FF',
            Color.INTENSE_RED: '#FF4444',
            Color.INTENSE_WHITE: '#FFFFFF',
            Color.INTENSE_YELLOW: '#FFFF44',
            Color.NO_COLOR: 'noinherit',
            Color.PURPLE: '#AA00AA',
            Color.RED: '#AA0000',
            Color.WHITE: '#888888',
            Color.YELLOW: '#AAAA00',
        }
    else:
        style = {
            Color.BLACK: '#000000',
            Color.BLUE: '#0000AA',
            Color.CYAN: '#00AAAA',
            Color.GREEN: '#00AA00',
            Color.INTENSE_BLACK: '#555555',
            Color.INTENSE_BLUE: '#0000FF',
            Color.INTENSE_CYAN: '#55FFFF',
            Color.INTENSE_GREEN: '#00FF00',
            Color.INTENSE_PURPLE: '#FF00FF',
            Color.INTENSE_RED: '#FF0000',
            Color.INTENSE_WHITE: '#ffffff',
            Color.INTENSE_YELLOW: '#FFFF55',
            Color.NO_COLOR: 'noinherit',
            Color.PURPLE: '#AA00AA',
            Color.RED: '#AA0000',
            Color.WHITE: '#aaaaaa',
            Color.YELLOW: '#ffff00',
        }
    _expand_style(style)
    return style


def _monokai_style():
    style = {
        Color.BLACK: '#1e0010',
        Color.BLUE: '#6666ef',
        Color.CYAN: '#66d9ef',
        Color.GREEN: '#2ee22e',
        Color.INTENSE_BLACK: '#5e5e5e',
        Color.INTENSE_BLUE: '#2626d7',
        Color.INTENSE_CYAN: '#2ed9d9',
        Color.INTENSE_GREEN: '#a6e22e',
        Color.INTENSE_PURPLE: '#ae81ff',
        Color.INTENSE_RED: '#f92672',
        Color.INTENSE_WHITE: '#f8f8f2',
        Color.INTENSE_YELLOW: '#e6db74',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#960050',
        Color.RED: '#AF0000',
        Color.WHITE: '#d7d7d7',
        Color.YELLOW: '#e2e22e',
    }
    _expand_style(style)
    return style


######################################
#   Auto-generated below this line   #
######################################
def _algol_style():
    style = {
        Color.BLACK: '#666',
        Color.BLUE: '#666',
        Color.CYAN: '#666',
        Color.GREEN: '#666',
        Color.INTENSE_BLACK: '#666',
        Color.INTENSE_BLUE: '#888',
        Color.INTENSE_CYAN: '#888',
        Color.INTENSE_GREEN: '#888',
        Color.INTENSE_PURPLE: '#888',
        Color.INTENSE_RED: '#FF0000',
        Color.INTENSE_WHITE: '#888',
        Color.INTENSE_YELLOW: '#888',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#666',
        Color.RED: '#FF0000',
        Color.WHITE: '#888',
        Color.YELLOW: '#FF0000',
        }
    _expand_style(style)
    return style


def _algol_nu_style():
    style = {
        Color.BLACK: '#666',
        Color.BLUE: '#666',
        Color.CYAN: '#666',
        Color.GREEN: '#666',
        Color.INTENSE_BLACK: '#666',
        Color.INTENSE_BLUE: '#888',
        Color.INTENSE_CYAN: '#888',
        Color.INTENSE_GREEN: '#888',
        Color.INTENSE_PURPLE: '#888',
        Color.INTENSE_RED: '#FF0000',
        Color.INTENSE_WHITE: '#888',
        Color.INTENSE_YELLOW: '#888',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#666',
        Color.RED: '#FF0000',
        Color.WHITE: '#888',
        Color.YELLOW: '#FF0000',
        }
    _expand_style(style)
    return style


def _autumn_style():
    style = {
        Color.BLACK: '#000080',
        Color.BLUE: '#0000aa',
        Color.CYAN: '#00aaaa',
        Color.GREEN: '#00aa00',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#1e90ff',
        Color.INTENSE_CYAN: '#1e90ff',
        Color.INTENSE_GREEN: '#4c8317',
        Color.INTENSE_PURPLE: '#FAA',
        Color.INTENSE_RED: '#aa5500',
        Color.INTENSE_WHITE: '#bbbbbb',
        Color.INTENSE_YELLOW: '#FAA',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#aa0000',
        Color.WHITE: '#aaaaaa',
        Color.YELLOW: '#aa5500',
        }
    _expand_style(style)
    return style


def _borland_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#000080',
        Color.CYAN: '#008080',
        Color.GREEN: '#008800',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#0000FF',
        Color.INTENSE_CYAN: '#ddffdd',
        Color.INTENSE_GREEN: '#888888',
        Color.INTENSE_PURPLE: '#e3d2d2',
        Color.INTENSE_RED: '#FF0000',
        Color.INTENSE_WHITE: '#ffdddd',
        Color.INTENSE_YELLOW: '#e3d2d2',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#aa0000',
        Color.WHITE: '#aaaaaa',
        Color.YELLOW: '#a61717',
        }
    _expand_style(style)
    return style


def _colorful_style():
    style = {
        Color.BLACK: '#000',
        Color.BLUE: '#00C',
        Color.CYAN: '#0e84b5',
        Color.GREEN: '#00A000',
        Color.INTENSE_BLACK: '#555',
        Color.INTENSE_BLUE: '#33B',
        Color.INTENSE_CYAN: '#bbbbbb',
        Color.INTENSE_GREEN: '#888',
        Color.INTENSE_PURPLE: '#FAA',
        Color.INTENSE_RED: '#D42',
        Color.INTENSE_WHITE: '#fff0ff',
        Color.INTENSE_YELLOW: '#FAA',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#A00000',
        Color.WHITE: '#bbbbbb',
        Color.YELLOW: '#A60',
        }
    _expand_style(style)
    return style


def _emacs_style():
    style = {
        Color.BLACK: '#008000',
        Color.BLUE: '#000080',
        Color.CYAN: '#04D',
        Color.GREEN: '#00A000',
        Color.INTENSE_BLACK: '#666666',
        Color.INTENSE_BLUE: '#04D',
        Color.INTENSE_CYAN: '#bbbbbb',
        Color.INTENSE_GREEN: '#00BB00',
        Color.INTENSE_PURPLE: '#AA22FF',
        Color.INTENSE_RED: '#D2413A',
        Color.INTENSE_WHITE: '#bbbbbb',
        Color.INTENSE_YELLOW: '#bbbbbb',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#A00000',
        Color.WHITE: '#bbbbbb',
        Color.YELLOW: '#BB6622',
        }
    _expand_style(style)
    return style


def _friendly_style():
    style = {
        Color.BLACK: '#007020',
        Color.BLUE: '#000080',
        Color.CYAN: '#0e84b5',
        Color.GREEN: '#00A000',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#70a0d0',
        Color.INTENSE_CYAN: '#60add5',
        Color.INTENSE_GREEN: '#40a070',
        Color.INTENSE_PURPLE: '#bb60d5',
        Color.INTENSE_RED: '#d55537',
        Color.INTENSE_WHITE: '#fff0f0',
        Color.INTENSE_YELLOW: '#bbbbbb',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#A00000',
        Color.WHITE: '#bbbbbb',
        Color.YELLOW: '#c65d09',
        }
    _expand_style(style)
    return style


def _fruity_style():
    style = {
        Color.BLACK: '#0f140f',
        Color.BLUE: '#0086d2',
        Color.CYAN: '#0086d2',
        Color.GREEN: '#008800',
        Color.INTENSE_BLACK: '#444444',
        Color.INTENSE_BLUE: '#0086f7',
        Color.INTENSE_CYAN: '#0086f7',
        Color.INTENSE_GREEN: '#888888',
        Color.INTENSE_PURPLE: '#ff0086',
        Color.INTENSE_RED: '#fb660a',
        Color.INTENSE_WHITE: '#ffffff',
        Color.INTENSE_YELLOW: '#cdcaa9',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#ff0086',
        Color.RED: '#ff0007',
        Color.WHITE: '#cdcaa9',
        Color.YELLOW: '#fb660a',
        }
    _expand_style(style)
    return style


def _igor_style():
    style = {
        Color.BLACK: '#009C00',
        Color.BLUE: '#0000FF',
        Color.CYAN: '#007575',
        Color.GREEN: '#009C00',
        Color.INTENSE_BLACK: '#007575',
        Color.INTENSE_BLUE: '#0000FF',
        Color.INTENSE_CYAN: '#007575',
        Color.INTENSE_GREEN: '#009C00',
        Color.INTENSE_PURPLE: '#CC00A3',
        Color.INTENSE_RED: '#C34E00',
        Color.INTENSE_WHITE: '#CC00A3',
        Color.INTENSE_YELLOW: '#C34E00',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#CC00A3',
        Color.RED: '#C34E00',
        Color.WHITE: '#CC00A3',
        Color.YELLOW: '#C34E00',
        }
    _expand_style(style)
    return style


def _lovelace_style():
    style = {
        Color.BLACK: '#444444',
        Color.BLUE: '#2838b0',
        Color.CYAN: '#289870',
        Color.GREEN: '#388038',
        Color.INTENSE_BLACK: '#666666',
        Color.INTENSE_BLUE: '#2838b0',
        Color.INTENSE_CYAN: '#888888',
        Color.INTENSE_GREEN: '#289870',
        Color.INTENSE_PURPLE: '#a848a8',
        Color.INTENSE_RED: '#b83838',
        Color.INTENSE_WHITE: '#888888',
        Color.INTENSE_YELLOW: '#a89028',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#a848a8',
        Color.RED: '#c02828',
        Color.WHITE: '#888888',
        Color.YELLOW: '#b85820',
        }
    _expand_style(style)
    return style


def _manni_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#000099',
        Color.CYAN: '#009999',
        Color.GREEN: '#00CC00',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#9999FF',
        Color.INTENSE_CYAN: '#00CCFF',
        Color.INTENSE_GREEN: '#99CC66',
        Color.INTENSE_PURPLE: '#CC00FF',
        Color.INTENSE_RED: '#FF6600',
        Color.INTENSE_WHITE: '#FFCCCC',
        Color.INTENSE_YELLOW: '#FFCC33',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#CC00FF',
        Color.RED: '#AA0000',
        Color.WHITE: '#AAAAAA',
        Color.YELLOW: '#CC3300',
        }
    _expand_style(style)
    return style


def _murphy_style():
    style = {
        Color.BLACK: '#000',
        Color.BLUE: '#000080',
        Color.CYAN: '#0e84b5',
        Color.GREEN: '#00A000',
        Color.INTENSE_BLACK: '#555',
        Color.INTENSE_BLUE: '#66f',
        Color.INTENSE_CYAN: '#5ed',
        Color.INTENSE_GREEN: '#5ed',
        Color.INTENSE_PURPLE: '#e9e',
        Color.INTENSE_RED: '#f84',
        Color.INTENSE_WHITE: '#eee',
        Color.INTENSE_YELLOW: '#fc8',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#A00000',
        Color.WHITE: '#bbbbbb',
        Color.YELLOW: '#c65d09',
        }
    _expand_style(style)
    return style


def _native_style():
    style = {
        Color.BLACK: '#520000',
        Color.BLUE: '#3677a9',
        Color.CYAN: '#24909d',
        Color.GREEN: '#589819',
        Color.INTENSE_BLACK: '#666666',
        Color.INTENSE_BLUE: '#447fcf',
        Color.INTENSE_CYAN: '#40ffff',
        Color.INTENSE_GREEN: '#6ab825',
        Color.INTENSE_PURPLE: '#e3d2d2',
        Color.INTENSE_RED: '#cd2828',
        Color.INTENSE_WHITE: '#ffffff',
        Color.INTENSE_YELLOW: '#ed9d13',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#666666',
        Color.RED: '#a61717',
        Color.WHITE: '#aaaaaa',
        Color.YELLOW: '#a61717',
        }
    _expand_style(style)
    return style


def _paraiso_dark_style():
    style = {
        Color.BLACK: '#776e71',
        Color.BLUE: '#815ba4',
        Color.CYAN: '#06b6ef',
        Color.GREEN: '#48b685',
        Color.INTENSE_BLACK: '#776e71',
        Color.INTENSE_BLUE: '#815ba4',
        Color.INTENSE_CYAN: '#5bc4bf',
        Color.INTENSE_GREEN: '#48b685',
        Color.INTENSE_PURPLE: '#e7e9db',
        Color.INTENSE_RED: '#ef6155',
        Color.INTENSE_WHITE: '#e7e9db',
        Color.INTENSE_YELLOW: '#fec418',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#815ba4',
        Color.RED: '#ef6155',
        Color.WHITE: '#5bc4bf',
        Color.YELLOW: '#f99b15',
        }
    _expand_style(style)
    return style


def _paraiso_light_style():
    style = {
        Color.BLACK: '#2f1e2e',
        Color.BLUE: '#2f1e2e',
        Color.CYAN: '#06b6ef',
        Color.GREEN: '#48b685',
        Color.INTENSE_BLACK: '#2f1e2e',
        Color.INTENSE_BLUE: '#815ba4',
        Color.INTENSE_CYAN: '#5bc4bf',
        Color.INTENSE_GREEN: '#48b685',
        Color.INTENSE_PURPLE: '#815ba4',
        Color.INTENSE_RED: '#ef6155',
        Color.INTENSE_WHITE: '#5bc4bf',
        Color.INTENSE_YELLOW: '#fec418',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#815ba4',
        Color.RED: '#2f1e2e',
        Color.WHITE: '#8d8687',
        Color.YELLOW: '#f99b15',
        }
    _expand_style(style)
    return style


def _pastie_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#0000DD',
        Color.CYAN: '#0066bb',
        Color.GREEN: '#008800',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#3333bb',
        Color.INTENSE_CYAN: '#ddffdd',
        Color.INTENSE_GREEN: '#22bb22',
        Color.INTENSE_PURPLE: '#e3d2d2',
        Color.INTENSE_RED: '#dd7700',
        Color.INTENSE_WHITE: '#fff0ff',
        Color.INTENSE_YELLOW: '#e3d2d2',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#bb0066',
        Color.RED: '#aa0000',
        Color.WHITE: '#bbbbbb',
        Color.YELLOW: '#aa6600',
        }
    _expand_style(style)
    return style


def _perldoc_style():
    style = {
        Color.BLACK: '#000080',
        Color.BLUE: '#000080',
        Color.CYAN: '#1e889b',
        Color.GREEN: '#00aa00',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#B452CD',
        Color.INTENSE_CYAN: '#bbbbbb',
        Color.INTENSE_GREEN: '#228B22',
        Color.INTENSE_PURPLE: '#B452CD',
        Color.INTENSE_RED: '#CD5555',
        Color.INTENSE_WHITE: '#e3d2d2',
        Color.INTENSE_YELLOW: '#e3d2d2',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#8B008B',
        Color.RED: '#aa0000',
        Color.WHITE: '#a7a7a7',
        Color.YELLOW: '#cb6c20',
        }
    _expand_style(style)
    return style


def _rrt_style():
    style = {
        Color.BLACK: '#ff0000',
        Color.BLUE: '#87ceeb',
        Color.CYAN: '#87ceeb',
        Color.GREEN: '#00ff00',
        Color.INTENSE_BLACK: '#87ceeb',
        Color.INTENSE_BLUE: '#87ceeb',
        Color.INTENSE_CYAN: '#7fffd4',
        Color.INTENSE_GREEN: '#00ff00',
        Color.INTENSE_PURPLE: '#ee82ee',
        Color.INTENSE_RED: '#ff0000',
        Color.INTENSE_WHITE: '#e5e5e5',
        Color.INTENSE_YELLOW: '#eedd82',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#ee82ee',
        Color.RED: '#ff0000',
        Color.WHITE: '#87ceeb',
        Color.YELLOW: '#ff0000',
        }
    _expand_style(style)
    return style


def _tango_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#0000cf',
        Color.CYAN: '#3465a4',
        Color.GREEN: '#00A000',
        Color.INTENSE_BLACK: '#204a87',
        Color.INTENSE_BLUE: '#5c35cc',
        Color.INTENSE_CYAN: '#f8f8f8',
        Color.INTENSE_GREEN: '#4e9a06',
        Color.INTENSE_PURPLE: '#f8f8f8',
        Color.INTENSE_RED: '#ef2929',
        Color.INTENSE_WHITE: '#f8f8f8',
        Color.INTENSE_YELLOW: '#c4a000',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#a40000',
        Color.WHITE: '#f8f8f8',
        Color.YELLOW: '#8f5902',
        }
    _expand_style(style)
    return style


def _trac_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#000080',
        Color.CYAN: '#009999',
        Color.GREEN: '#808000',
        Color.INTENSE_BLACK: '#555555',
        Color.INTENSE_BLUE: '#445588',
        Color.INTENSE_CYAN: '#ddffdd',
        Color.INTENSE_GREEN: '#999988',
        Color.INTENSE_PURPLE: '#e3d2d2',
        Color.INTENSE_RED: '#bb8844',
        Color.INTENSE_WHITE: '#ffdddd',
        Color.INTENSE_YELLOW: '#e3d2d2',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#800080',
        Color.RED: '#aa0000',
        Color.WHITE: '#aaaaaa',
        Color.YELLOW: '#808000',
        }
    _expand_style(style)
    return style


def _vim_style():
    style = {
        Color.BLACK: '#000080',
        Color.BLUE: '#000080',
        Color.CYAN: '#00cdcd',
        Color.GREEN: '#00cd00',
        Color.INTENSE_BLACK: '#666699',
        Color.INTENSE_BLUE: '#3399cc',
        Color.INTENSE_CYAN: '#00cdcd',
        Color.INTENSE_GREEN: '#00cd00',
        Color.INTENSE_PURPLE: '#cd00cd',
        Color.INTENSE_RED: '#FF0000',
        Color.INTENSE_WHITE: '#cccccc',
        Color.INTENSE_YELLOW: '#cdcd00',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#cd00cd',
        Color.RED: '#cd0000',
        Color.WHITE: '#cccccc',
        Color.YELLOW: '#cd0000',
        }
    _expand_style(style)
    return style


def _vs_style():
    style = {
        Color.BLACK: '#008000',
        Color.BLUE: '#0000ff',
        Color.CYAN: '#2b91af',
        Color.GREEN: '#008000',
        Color.INTENSE_BLACK: '#2b91af',
        Color.INTENSE_BLUE: '#2b91af',
        Color.INTENSE_CYAN: '#2b91af',
        Color.INTENSE_GREEN: '#2b91af',
        Color.INTENSE_PURPLE: '#2b91af',
        Color.INTENSE_RED: '#FF0000',
        Color.INTENSE_WHITE: '#2b91af',
        Color.INTENSE_YELLOW: '#2b91af',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#a31515',
        Color.RED: '#a31515',
        Color.WHITE: '#2b91af',
        Color.YELLOW: '#a31515',
        }
    _expand_style(style)
    return style


def _xcode_style():
    style = {
        Color.BLACK: '#000000',
        Color.BLUE: '#1C01CE',
        Color.CYAN: '#3F6E75',
        Color.GREEN: '#177500',
        Color.INTENSE_BLACK: '#3F6E75',
        Color.INTENSE_BLUE: '#2300CE',
        Color.INTENSE_CYAN: '#3F6E75',
        Color.INTENSE_GREEN: '#3F6E75',
        Color.INTENSE_PURPLE: '#A90D91',
        Color.INTENSE_RED: '#C41A16',
        Color.INTENSE_WHITE: '#3F6E75',
        Color.INTENSE_YELLOW: '#836C28',
        Color.NO_COLOR: 'noinherit',
        Color.PURPLE: '#A90D91',
        Color.RED: '#C41A16',
        Color.WHITE: '#3F6E75',
        Color.YELLOW: '#836C28',
        }
    _expand_style(style)
    return style


STYLES = LazyDict({
    'algol': _algol_style,
    'algol_nu': _algol_nu_style,
    'autumn': _autumn_style,
    'borland': _borland_style,
    'bw': _bw_style,
    'colorful': _colorful_style,
    'default': _default_style,
    'emacs': _emacs_style,
    'friendly': _friendly_style,
    'fruity': _fruity_style,
    'igor': _igor_style,
    'lovelace': _lovelace_style,
    'manni': _manni_style,
    'monokai': _monokai_style,
    'murphy': _murphy_style,
    'native': _native_style,
    'paraiso-dark': _paraiso_dark_style,
    'paraiso-light': _paraiso_light_style,
    'pastie': _pastie_style,
    'perldoc': _perldoc_style,
    'rrt': _rrt_style,
    'tango': _tango_style,
    'trac': _trac_style,
    'vim': _vim_style,
    'vs': _vs_style,
    'xcode': _xcode_style,
    }, globals(), 'STYLES')

del (_algol_style, _algol_nu_style, _autumn_style, _borland_style, _bw_style,
     _colorful_style, _default_style, _emacs_style, _friendly_style,
     _fruity_style, _igor_style, _lovelace_style, _manni_style, _monokai_style,
     _murphy_style, _native_style, _paraiso_dark_style, _paraiso_light_style,
     _pastie_style, _perldoc_style, _rrt_style, _tango_style, _trac_style,
     _vim_style, _vs_style, _xcode_style)


# dynamic syles
def make_pygments_style(pallette):
    """Makes a pygments style based on a color pallete."""
    global Color
    style = {getattr(Color, 'NO_COLOR'): 'noinherit'}
    for name, t in BASE_XONSH_COLORS.items():
        color = find_closest_color(t, pallette)
        style[getattr(Color, name)] = '#' + color
        style[getattr(Color, 'BOLD_'+name)] = 'bold #' + color
        style[getattr(Color, 'UNDERLINE_'+name)] = 'underline #' + color
        style[getattr(Color, 'BOLD_UNDERLINE_'+name)] = 'bold underline #' + color
        style[getattr(Color, 'BACKGROUND_'+name)] = 'bg:#' + color
    return style


def pygments_style_by_name(name):
    """Gets or makes a pygments color style by its name."""
    if name in STYLES:
        return STYLES[name]
    pstyle = get_style_by_name(name)
    pallette = make_pallete(pstyle.styles.values())
    astyle = make_pygments_style(pallette)
    STYLES[name] = astyle
    return astyle


#
# Formatter
#

@lazyobject
def XonshTerminal256Formatter():
    class XonshTerminal256FormatterProxy(terminal256.Terminal256Formatter):
        """Proxy class for xonsh terminal256 formatting that understands.
        xonsh color tokens.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # just keep the opening token for colors.
            color_names = set(map(str, Color.subtypes))
            for name, (opener, closer) in self.style_string.items():
                if name in color_names:
                    self.style_string[name] = (opener, '')
            # special case NO_COLOR, because it is special.
            self.style_string['Token.Color.NO_COLOR'] = ('\x1b[39m', '')

    return XonshTerminal256FormatterProxy
