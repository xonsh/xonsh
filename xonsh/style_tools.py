"""Xonsh color styling tools that simulate pygments, when it is unavailable."""
import builtins
import string

from xonsh.platform import HAS_PYGMENTS
from xonsh.lazyasd import LazyObject
from xonsh.color_tools import RE_BACKGROUND


class _TokenType(tuple):
    """
    Forked from the pygments project
    https://bitbucket.org/birkenfeld/pygments-main
    Copyright (c) 2006-2017 by the respective authors, All rights reserved.
    See https://bitbucket.org/birkenfeld/pygments-main/raw/05818a4ef9891d9ac22c851f7b3ea4b4fce460ab/AUTHORS
    """
    parent = None

    def split(self):
        buf = []
        node = self
        while node is not None:
            buf.append(node)
            node = node.parent
        buf.reverse()
        return buf

    def __init__(self, *args):
        # no need to call super.__init__
        self.subtypes = set()

    def __contains__(self, val):
        return self is val or (
            type(val) is self.__class__ and
            val[:len(self)] == self
        )

    def __getattr__(self, val):
        if not val or not val[0].isupper():
            return tuple.__getattribute__(self, val)
        new = _TokenType(self + (val,))
        setattr(self, val, new)
        self.subtypes.add(new)
        new.parent = self
        return new

    def __repr__(self):
        return 'Token' + (self and '.' or '') + '.'.join(self)

    def __copy__(self):
        # These instances are supposed to be singletons
        return self

    def __deepcopy__(self, memo):
        # These instances are supposed to be singletons
        return self


Token = _TokenType()
Color = Token.Color


def partial_color_tokenize(template):
    """Tokenizes a template string containing colors. Will return a list
    of tuples mapping the token to the string which has that color.
    These sub-strings maybe templates themselves.
    """
    if HAS_PYGMENTS and hasattr(builtins, '__xonsh_shell__'):
        styles = __xonsh_shell__.shell.styler.styles
    elif hasattr(builtins, '__xonsh_shell__'):
        styles = DEFAULT_STYLE_DICT
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


def norm_name(name):
    """Normalizes a color name."""
    return name.replace('#', 'HEX').replace('BGHEX', 'BACKGROUND_HEX')

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

DEFAULT_STYLE_DICT = LazyObject(lambda: {
    Token: '',
    Token.Aborted: '#ansidarkgray',
    Token.AutoSuggestion: '#ansidarkgray',
    Token.Color.BACKGROUND_BLACK: 'bg:#ansiblack',
    Token.Color.BACKGROUND_BLUE: 'bg:#ansidarkblue',
    Token.Color.BACKGROUND_CYAN: 'bg:#ansiteal',
    Token.Color.BACKGROUND_GREEN: 'bg:#ansidarkgreen',
    Token.Color.BACKGROUND_INTENSE_BLACK: 'bg:#ansidarkgray',
    Token.Color.BACKGROUND_INTENSE_BLUE: 'bg:#ansiblue',
    Token.Color.BACKGROUND_INTENSE_CYAN: 'bg:#ansiturquoise',
    Token.Color.BACKGROUND_INTENSE_GREEN: 'bg:#ansigreen',
    Token.Color.BACKGROUND_INTENSE_PURPLE: 'bg:#ansifuchsia',
    Token.Color.BACKGROUND_INTENSE_RED: 'bg:#ansired',
    Token.Color.BACKGROUND_INTENSE_WHITE: 'bg:#ansiwhite',
    Token.Color.BACKGROUND_INTENSE_YELLOW: 'bg:#ansiyellow',
    Token.Color.BACKGROUND_PURPLE: 'bg:#ansipurple',
    Token.Color.BACKGROUND_RED: 'bg:#ansidarkred',
    Token.Color.BACKGROUND_WHITE: 'bg:#ansilightgray',
    Token.Color.BACKGROUND_YELLOW: 'bg:#ansibrown',
    Token.Color.BLACK: '#ansiblack',
    Token.Color.BLUE: '#ansidarkblue',
    Token.Color.BOLD_BLACK: 'bold #ansiblack',
    Token.Color.BOLD_BLUE: 'bold #ansidarkblue',
    Token.Color.BOLD_CYAN: 'bold #ansiteal',
    Token.Color.BOLD_GREEN: 'bold #ansidarkgreen',
    Token.Color.BOLD_INTENSE_BLACK: 'bold #ansidarkgray',
    Token.Color.BOLD_INTENSE_BLUE: 'bold #ansiblue',
    Token.Color.BOLD_INTENSE_CYAN: 'bold #ansiturquoise',
    Token.Color.BOLD_INTENSE_GREEN: 'bold #ansigreen',
    Token.Color.BOLD_INTENSE_PURPLE: 'bold #ansifuchsia',
    Token.Color.BOLD_INTENSE_RED: 'bold #ansired',
    Token.Color.BOLD_INTENSE_WHITE: 'bold #ansiwhite',
    Token.Color.BOLD_INTENSE_YELLOW: 'bold #ansiyellow',
    Token.Color.BOLD_PURPLE: 'bold #ansipurple',
    Token.Color.BOLD_RED: 'bold #ansidarkred',
    Token.Color.BOLD_UNDERLINE_BLACK: 'bold underline #ansiblack',
    Token.Color.BOLD_UNDERLINE_BLUE: 'bold underline #ansidarkblue',
    Token.Color.BOLD_UNDERLINE_CYAN: 'bold underline #ansiteal',
    Token.Color.BOLD_UNDERLINE_GREEN: 'bold underline #ansidarkgreen',
    Token.Color.BOLD_UNDERLINE_INTENSE_BLACK: 'bold underline #ansidarkgray',
    Token.Color.BOLD_UNDERLINE_INTENSE_BLUE: 'bold underline #ansiblue',
    Token.Color.BOLD_UNDERLINE_INTENSE_CYAN: 'bold underline #ansiturquoise',
    Token.Color.BOLD_UNDERLINE_INTENSE_GREEN: 'bold underline #ansigreen',
    Token.Color.BOLD_UNDERLINE_INTENSE_PURPLE: 'bold underline #ansifuchsia',
    Token.Color.BOLD_UNDERLINE_INTENSE_RED: 'bold underline #ansired',
    Token.Color.BOLD_UNDERLINE_INTENSE_WHITE: 'bold underline #ansiwhite',
    Token.Color.BOLD_UNDERLINE_INTENSE_YELLOW: 'bold underline #ansiyellow',
    Token.Color.BOLD_UNDERLINE_PURPLE: 'bold underline #ansipurple',
    Token.Color.BOLD_UNDERLINE_RED: 'bold underline #ansidarkred',
    Token.Color.BOLD_UNDERLINE_WHITE: 'bold underline #ansilightgray',
    Token.Color.BOLD_UNDERLINE_YELLOW: 'bold underline #ansibrown',
    Token.Color.BOLD_WHITE: 'bold #ansilightgray',
    Token.Color.BOLD_YELLOW: 'bold #ansibrown',
    Token.Color.CYAN: '#ansiteal',
    Token.Color.GREEN: '#ansidarkgreen',
    Token.Color.INTENSE_BLACK: '#ansidarkgray',
    Token.Color.INTENSE_BLUE: '#ansiblue',
    Token.Color.INTENSE_CYAN: '#ansiturquoise',
    Token.Color.INTENSE_GREEN: '#ansigreen',
    Token.Color.INTENSE_PURPLE: '#ansifuchsia',
    Token.Color.INTENSE_RED: '#ansired',
    Token.Color.INTENSE_WHITE: '#ansiwhite',
    Token.Color.INTENSE_YELLOW: '#ansiyellow',
    Token.Color.NO_COLOR: 'noinherit',
    Token.Color.PURPLE: '#ansipurple',
    Token.Color.RED: '#ansidarkred',
    Token.Color.UNDERLINE_BLACK: 'underline #ansiblack',
    Token.Color.UNDERLINE_BLUE: 'underline #ansidarkblue',
    Token.Color.UNDERLINE_CYAN: 'underline #ansiteal',
    Token.Color.UNDERLINE_GREEN: 'underline #ansidarkgreen',
    Token.Color.UNDERLINE_INTENSE_BLACK: 'underline #ansidarkgray',
    Token.Color.UNDERLINE_INTENSE_BLUE: 'underline #ansiblue',
    Token.Color.UNDERLINE_INTENSE_CYAN: 'underline #ansiturquoise',
    Token.Color.UNDERLINE_INTENSE_GREEN: 'underline #ansigreen',
    Token.Color.UNDERLINE_INTENSE_PURPLE: 'underline #ansifuchsia',
    Token.Color.UNDERLINE_INTENSE_RED: 'underline #ansired',
    Token.Color.UNDERLINE_INTENSE_WHITE: 'underline #ansiwhite',
    Token.Color.UNDERLINE_INTENSE_YELLOW: 'underline #ansiyellow',
    Token.Color.UNDERLINE_PURPLE: 'underline #ansipurple',
    Token.Color.UNDERLINE_RED: 'underline #ansidarkred',
    Token.Color.UNDERLINE_WHITE: 'underline #ansilightgray',
    Token.Color.UNDERLINE_YELLOW: 'underline #ansibrown',
    Token.Color.WHITE: '#ansilightgray',
    Token.Color.YELLOW: '#ansibrown',
    Token.Comment: 'underline #ansiteal',
    Token.Comment.Hashbang: '',
    Token.Comment.Multiline: '',
    Token.Comment.Preproc: 'underline #ansibrown',
    Token.Comment.PreprocFile: '',
    Token.Comment.Single: '',
    Token.Comment.Special: '',
    Token.Error: '#ansired',
    Token.Escape: '',
    Token.Generic: '',
    Token.Generic.Deleted: '#ansidarkred',
    Token.Generic.Emph: 'underline',
    Token.Generic.Error: 'bold #ansired',
    Token.Generic.Heading: 'bold #ansidarkblue',
    Token.Generic.Inserted: '#ansigreen',
    Token.Generic.Output: '#ansidarkblue',
    Token.Generic.Prompt: 'bold #ansidarkblue',
    Token.Generic.Strong: '',
    Token.Generic.Subheading: 'bold #ansipurple',
    Token.Generic.Traceback: '#ansidarkblue',
    Token.Keyword: 'bold #ansidarkgreen',
    Token.Keyword.Constant: '',
    Token.Keyword.Declaration: '',
    Token.Keyword.Namespace: '',
    Token.Keyword.Pseudo: 'nobold',
    Token.Keyword.Reserved: '',
    Token.Keyword.Type: 'nobold #ansidarkred',
    Token.Literal: '',
    Token.Literal.Date: '',
    Token.Literal.Number: '#ansidarkgray',
    Token.Literal.Number.Bin: '',
    Token.Literal.Number.Float: '',
    Token.Literal.Number.Hex: '',
    Token.Literal.Number.Integer: '',
    Token.Literal.Number.Integer.Long: '',
    Token.Literal.Number.Oct: '',
    Token.Literal.String: '#ansired',
    Token.Literal.String.Affix: '',
    Token.Literal.String.Backtick: '',
    Token.Literal.String.Char: '',
    Token.Literal.String.Delimiter: '',
    Token.Literal.String.Doc: 'underline',
    Token.Literal.String.Double: '',
    Token.Literal.String.Escape: 'bold #ansibrown',
    Token.Literal.String.Heredoc: '',
    Token.Literal.String.Interpol: 'bold #ansipurple',
    Token.Literal.String.Other: '#ansidarkgreen',
    Token.Literal.String.Regex: '#ansipurple',
    Token.Literal.String.Single: '',
    Token.Literal.String.Symbol: '#ansibrown',
    Token.Menu.Completions: 'bg:#ansilightgray #ansiblack',
    Token.Menu.Completions.Completion: '',
    Token.Menu.Completions.Completion.Current: 'bg:#ansidarkgray #ansiwhite',
    Token.Name: '',
    Token.Name.Attribute: '#ansiyellow',
    Token.Name.Builtin: '#ansidarkgreen',
    Token.Name.Builtin.Pseudo: '',
    Token.Name.Class: 'bold #ansiblue',
    Token.Name.Constant: '#ansidarkred',
    Token.Name.Decorator: '#ansifuchsia',
    Token.Name.Entity: 'bold #ansilightgray',
    Token.Name.Exception: 'bold #ansired',
    Token.Name.Function: '#ansiblue',
    Token.Name.Function.Magic: '',
    Token.Name.Label: '#ansiyellow',
    Token.Name.Namespace: 'bold #ansiblue',
    Token.Name.Other: '',
    Token.Name.Property: '',
    Token.Name.Tag: 'bold #ansidarkgreen',
    Token.Name.Variable: '#ansidarkblue',
    Token.Name.Variable.Class: '',
    Token.Name.Variable.Global: '',
    Token.Name.Variable.Instance: '',
    Token.Name.Variable.Magic: '',
    Token.Operator: '#ansidarkgray',
    Token.Operator.Word: 'bold #ansipurple',
    Token.Other: '',
    Token.Punctuation: '',
    Token.Scrollbar: 'bg:#ansidarkgray',
    Token.Scrollbar.Arrow: 'bg:#ansiblack #ansiwhite bold',
    Token.Scrollbar.Button: 'bg:#ansiblack',
    Token.Text: '',
    Token.Text.Whitespace: '#ansilightgray'},
                                globals(), 'DEFAULT_STYLE_DICT')
