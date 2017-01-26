import re
import builtins
import string

from xonsh.lazyasd import LazyObject

class _TokenType(tuple):
    """
    Forked from mainline PTK
    """
    def __getattr__(self, val):
        if not val or not val[0].isupper():
            return tuple.__getattribute__(self, val)

        new = _TokenType(self + (val,))
        setattr(self, val, new)
        return new

    def __repr__(self):
        return 'Token' + (self and '.' or '') + '.'.join(self)

RE_BACKGROUND = LazyObject(lambda: re.compile('(BG#|BGHEX|BACKGROUND)'),
                           globals(), 'RE_BACKGROUND')

Token = _TokenType()
Color = Token.Color

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
