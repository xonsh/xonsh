import re


from xonsh.lazyasd import load_module_in_background

try:
    load_module_in_background('pkg_resources', debug='XONSH_DEBUG',
    replacements={'pygments.plugin': 'pkg_resources'})
    from pygments.token import (Keyword, Name, Comment, String, Error, Number,
                                Operator, Generic, Whitespace, Token)

except ImportError:
    from prompt_toolkit.token import Token
    (Keyword, Name, Comment, String,
     Error, Number, Operator, Generic, Whitespace) = (Token.Keyword,
                                                      Token.Name,
                                                      Token.Comment,
                                                      Token.String,
                                                      Token.Error,
                                                      Token.Number,
                                                      Token.Operator,
                                                      Token.Generic,
                                                      Token.Whitespace)

from xonsh.lazyasd import LazyObject

RE_BACKGROUND = LazyObject(lambda: re.compile('(BG#|BGHEX|BACKGROUND)'),
                           globals(), 'RE_BACKGROUND')

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

PTK_STYLE = {
    Token.Menu.Completions.Completion.Current: 'bg:#00aaaa #000000',
    Token.Menu.Completions.Completion: 'bg:#008888 #ffffff',
    Token.Menu.Completions.ProgressButton: 'bg:#003333',
    Token.Menu.Completions.ProgressBar: 'bg:#00aaaa',
    Token.AutoSuggestion: '#666666',
    Token.Aborted: '#888888',
}

XONSH_BASE_STYLE = LazyObject(lambda: {
    Whitespace: '#008080',
    Comment: 'underline',
    Comment.Preproc: 'underline',
    Keyword: 'bold',
    Keyword.Pseudo: '#008000',
    Keyword.Type: '',
    Operator: '#008080',
    Operator.Word: 'bold',
    Name.Builtin: '',
    Name.Function: '#000080',
    Name.Class: 'bold',
    Name.Namespace: 'bold',
    Name.Exception: 'bold',
    Name.Variable: '#008080',
    Name.Constant: '#800000',
    Name.Label: '#808000',
    Name.Entity: 'bold',
    Name.Attribute: '#008080',
    Name.Tag: 'bold',
    Name.Decorator: '#008080',
    String: '',
    String.Doc: 'underline',
    String.Interpol: 'bold',
    String.Escape: 'bold',
    String.Regex: '',
    String.Symbol: '',
    String.Other: '#008000',
    Number: '#800000',
    Generic.Heading: 'bold',
    Generic.Subheading: 'bold',
    Generic.Deleted: '#800000',
    Generic.Inserted: '#008000',
    Generic.Error: 'bold',
    Generic.Emph: 'underline',
    Generic.Prompt: 'bold',
    Generic.Output: '#008080',
    Generic.Traceback: '#800000',
    Error: '#800000',
    }, globals(), 'XONSH_BASE_STYLE')

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


def norm_name(name):
    """Normalizes a color name."""
    return name.replace('#', 'HEX').replace('BGHEX', 'BACKGROUND_HEX')
