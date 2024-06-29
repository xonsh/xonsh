"""Xonsh color styling tools that simulate pygments, when it is unavailable."""

from collections import defaultdict

from xonsh.color_tools import RE_BACKGROUND, iscolor, warn_deprecated_no_color
from xonsh.lib.lazyasd import LazyObject
from xonsh.platform import HAS_PYGMENTS
from xonsh.tools import FORMATTER


class _TokenType(tuple):
    """
    Forked from the pygments project
    https://bitbucket.org/birkenfeld/pygments-main
    Copyright (c) 2006-2017 by the respective authors, All rights reserved.
    See https://bitbucket.org/birkenfeld/pygments-main/raw/05818a4ef9891d9ac22c851f7b3ea4b4fce460ab/AUTHORS
    """

    parent: "_TokenType|None" = None

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
        return self is val or (type(val) is self.__class__ and val[: len(self)] == self)

    def __getattr__(self, val):
        if not val or not val[0].isupper():
            return tuple.__getattribute__(self, val)
        new = _TokenType(self + (val,))
        setattr(self, val, new)
        self.subtypes.add(new)
        new.parent = self
        return new

    def __repr__(self):
        return "Token" + (self and "." or "") + ".".join(self)

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
    from xonsh.built_ins import XSH

    if HAS_PYGMENTS and XSH.shell is not None:
        styles = XSH.shell.shell.styler.styles
    elif XSH.shell is not None:
        styles = DEFAULT_STYLE_DICT
    else:
        styles = None
    color = Color.RESET
    try:
        toks, color = _partial_color_tokenize_main(template, styles)
    except Exception:
        toks = [(Color.RESET, template)]
    if styles is not None:
        styles[color]  # ensure color is available
    return toks


def _partial_color_tokenize_main(template, styles):
    bopen = "{"
    bclose = "}"
    colon = ":"
    expl = "!"
    color = Color.RESET
    fg = bg = None
    value = ""
    toks = []
    for literal, field, spec, conv in FORMATTER.parse(template):
        if field is None:
            value += literal
        elif iscolor(field):
            value += literal
            next_color, fg, bg = color_by_name(field, fg, bg)
            if next_color is not color:
                if len(value) > 0:
                    toks.append((color, value))
                    if styles is not None:
                        styles[color]  # ensure color is available
                color = next_color
                value = ""
        elif field is not None:
            parts = [literal, bopen, field]
            if conv is not None and len(conv) > 0:
                parts.append(expl)
                parts.append(conv)
            if spec is not None and len(spec) > 0:
                parts.append(colon)
                parts.append(spec)
            parts.append(bclose)
            value += "".join(parts)
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
    if name in ("RESET", "NO_COLOR"):
        if name == "NO_COLOR":
            warn_deprecated_no_color()
        return Color.RESET, None, None
    m = RE_BACKGROUND.search(name)
    if m is None:  # must be foreground color
        fg = norm_name(name)
    else:
        bg = norm_name(name)
    # assemble token
    if fg is None and bg is None:
        tokname = "RESET"
    elif fg is None:
        tokname = bg
    elif bg is None:
        tokname = fg
    else:
        tokname = fg + "__" + bg
    tok = getattr(Color, tokname)
    return tok, fg, bg


def norm_name(name):
    """Normalizes a color name."""
    return name.upper().replace("#", "HEX")


def style_as_faded(template: str) -> str:
    """Remove the colors from the template string and style as faded."""
    tokens = partial_color_tokenize(template)
    without_color = "".join([str(sect) for _, sect in tokens])
    return "{RESET}{#d3d3d3}" + without_color + "{RESET}"


DEFAULT_STYLE_DICT = LazyObject(
    lambda: defaultdict(
        lambda: "",
        {
            Token: "",
            Token.Color.BACKGROUND_BLACK: "bg:ansiblack",
            Token.Color.BACKGROUND_BLUE: "bg:ansiblue",
            Token.Color.BACKGROUND_CYAN: "bg:ansicyan",
            Token.Color.BACKGROUND_GREEN: "bg:ansigreen",
            Token.Color.BACKGROUND_INTENSE_BLACK: "bg:ansibrightblack",
            Token.Color.BACKGROUND_INTENSE_BLUE: "bg:ansibrightblue",
            Token.Color.BACKGROUND_INTENSE_CYAN: "bg:ansibrightcyan",
            Token.Color.BACKGROUND_INTENSE_GREEN: "bg:ansibrightgreen",
            Token.Color.BACKGROUND_INTENSE_PURPLE: "bg:ansibrightmagenta",
            Token.Color.BACKGROUND_INTENSE_RED: "bg:ansibrightred",
            Token.Color.BACKGROUND_INTENSE_WHITE: "bg:ansiwhite",
            Token.Color.BACKGROUND_INTENSE_YELLOW: "bg:ansibrightyellow",
            Token.Color.BACKGROUND_PURPLE: "bg:ansimagenta",
            Token.Color.BACKGROUND_RED: "bg:ansired",
            Token.Color.BACKGROUND_WHITE: "bg:ansigray",
            Token.Color.BACKGROUND_YELLOW: "bg:ansiyellow",
            Token.Color.BLACK: "ansiblack",
            Token.Color.BLUE: "ansiblue",
            Token.Color.BOLD_BLACK: "bold ansiblack",
            Token.Color.BOLD_BLUE: "bold ansiblue",
            Token.Color.BOLD_CYAN: "bold ansicyan",
            Token.Color.BOLD_GREEN: "bold ansigreen",
            Token.Color.BOLD_INTENSE_BLACK: "bold ansibrightblack",
            Token.Color.BOLD_INTENSE_BLUE: "bold ansibrightblue",
            Token.Color.BOLD_INTENSE_CYAN: "bold ansibrightcyan",
            Token.Color.BOLD_INTENSE_GREEN: "bold ansibrightgreen",
            Token.Color.BOLD_INTENSE_PURPLE: "bold ansibrightmagenta",
            Token.Color.BOLD_INTENSE_RED: "bold ansibrightred",
            Token.Color.BOLD_INTENSE_WHITE: "bold ansiwhite",
            Token.Color.BOLD_INTENSE_YELLOW: "bold ansibrightyellow",
            Token.Color.BOLD_PURPLE: "bold ansimagenta",
            Token.Color.BOLD_RED: "bold ansired",
            Token.Color.BOLD_UNDERLINE_BLACK: "bold underline ansiblack",
            Token.Color.BOLD_UNDERLINE_BLUE: "bold underline ansiblue",
            Token.Color.BOLD_UNDERLINE_CYAN: "bold underline ansicyan",
            Token.Color.BOLD_UNDERLINE_GREEN: "bold underline ansigreen",
            Token.Color.BOLD_UNDERLINE_INTENSE_BLACK: "bold underline ansibrightblack",
            Token.Color.BOLD_UNDERLINE_INTENSE_BLUE: "bold underline ansibrightblue",
            Token.Color.BOLD_UNDERLINE_INTENSE_CYAN: "bold underline ansibrightcyan",
            Token.Color.BOLD_UNDERLINE_INTENSE_GREEN: "bold underline ansibrightgreen",
            Token.Color.BOLD_UNDERLINE_INTENSE_PURPLE: "bold underline ansibrightmagenta",
            Token.Color.BOLD_UNDERLINE_INTENSE_RED: "bold underline ansibrightred",
            Token.Color.BOLD_UNDERLINE_INTENSE_WHITE: "bold underline ansiwhite",
            Token.Color.BOLD_UNDERLINE_INTENSE_YELLOW: "bold underline ansibrightyellow",
            Token.Color.BOLD_UNDERLINE_PURPLE: "bold underline ansimagenta",
            Token.Color.BOLD_UNDERLINE_RED: "bold underline ansired",
            Token.Color.BOLD_UNDERLINE_WHITE: "bold underline ansigray",
            Token.Color.BOLD_UNDERLINE_YELLOW: "bold underline ansiyellow",
            Token.Color.BOLD_WHITE: "bold ansigray",
            Token.Color.BOLD_YELLOW: "bold ansiyellow",
            Token.Color.CYAN: "ansicyan",
            Token.Color.GREEN: "ansigreen",
            Token.Color.INTENSE_BLACK: "ansibrightblack",
            Token.Color.INTENSE_BLUE: "ansibrightblue",
            Token.Color.INTENSE_CYAN: "ansibrightcyan",
            Token.Color.INTENSE_GREEN: "ansibrightgreen",
            Token.Color.INTENSE_PURPLE: "ansibrightmagenta",
            Token.Color.INTENSE_RED: "ansibrightred",
            Token.Color.INTENSE_WHITE: "ansiwhite",
            Token.Color.INTENSE_YELLOW: "ansibrightyellow",
            Token.Color.RESET: "noinherit",
            Token.Color.PURPLE: "ansimagenta",
            Token.Color.RED: "ansired",
            Token.Color.UNDERLINE_BLACK: "underline ansiblack",
            Token.Color.UNDERLINE_BLUE: "underline ansiblue",
            Token.Color.UNDERLINE_CYAN: "underline ansicyan",
            Token.Color.UNDERLINE_GREEN: "underline ansigreen",
            Token.Color.UNDERLINE_INTENSE_BLACK: "underline ansibrightblack",
            Token.Color.UNDERLINE_INTENSE_BLUE: "underline ansibrightblue",
            Token.Color.UNDERLINE_INTENSE_CYAN: "underline ansibrightcyan",
            Token.Color.UNDERLINE_INTENSE_GREEN: "underline ansibrightgreen",
            Token.Color.UNDERLINE_INTENSE_PURPLE: "underline ansibrightmagenta",
            Token.Color.UNDERLINE_INTENSE_RED: "underline ansibrightred",
            Token.Color.UNDERLINE_INTENSE_WHITE: "underline ansiwhite",
            Token.Color.UNDERLINE_INTENSE_YELLOW: "underline ansibrightyellow",
            Token.Color.UNDERLINE_PURPLE: "underline ansimagenta",
            Token.Color.UNDERLINE_RED: "underline ansired",
            Token.Color.UNDERLINE_WHITE: "underline ansigray",
            Token.Color.UNDERLINE_YELLOW: "underline ansiyellow",
            Token.Color.WHITE: "ansigray",
            Token.Color.YELLOW: "ansiyellow",
            Token.Comment: "underline ansicyan",
            Token.Comment.Hashbang: "",
            Token.Comment.Multiline: "",
            Token.Comment.Preproc: "underline ansiyellow",
            Token.Comment.PreprocFile: "",
            Token.Comment.Single: "",
            Token.Comment.Special: "",
            Token.Error: "ansibrightred",
            Token.Escape: "",
            Token.Generic: "",
            Token.Generic.Deleted: "ansired",
            Token.Generic.Emph: "underline",
            Token.Generic.Error: "bold ansibrightred",
            Token.Generic.Heading: "bold ansiblue",
            Token.Generic.Inserted: "ansibrightgreen",
            Token.Generic.Output: "ansiblue",
            Token.Generic.Prompt: "bold ansiblue",
            Token.Generic.Strong: "",
            Token.Generic.Subheading: "bold ansimagenta",
            Token.Generic.Traceback: "ansiblue",
            Token.Keyword: "bold ansigreen",
            Token.Keyword.Constant: "",
            Token.Keyword.Declaration: "",
            Token.Keyword.Namespace: "",
            Token.Keyword.Pseudo: "nobold",
            Token.Keyword.Reserved: "",
            Token.Keyword.Type: "nobold ansired",
            Token.Literal: "",
            Token.Literal.Date: "",
            Token.Literal.Number: "ansibrightblack",
            Token.Literal.Number.Bin: "",
            Token.Literal.Number.Float: "",
            Token.Literal.Number.Hex: "",
            Token.Literal.Number.Integer: "",
            Token.Literal.Number.Integer.Long: "",
            Token.Literal.Number.Oct: "",
            Token.Literal.String: "ansibrightred",
            Token.Literal.String.Affix: "",
            Token.Literal.String.Backtick: "",
            Token.Literal.String.Char: "",
            Token.Literal.String.Delimiter: "",
            Token.Literal.String.Doc: "underline",
            Token.Literal.String.Double: "",
            Token.Literal.String.Escape: "bold ansiyellow",
            Token.Literal.String.Heredoc: "",
            Token.Literal.String.Interpol: "bold ansimagenta",
            Token.Literal.String.Other: "ansigreen",
            Token.Literal.String.Regex: "ansimagenta",
            Token.Literal.String.Single: "",
            Token.Literal.String.Symbol: "ansiyellow",
            Token.Name: "",
            Token.Name.Attribute: "ansibrightyellow",
            Token.Name.Builtin: "ansigreen",
            Token.Name.Builtin.Pseudo: "",
            Token.Name.Class: "bold ansibrightblue",
            Token.Name.Constant: "ansired",
            Token.Name.Decorator: "ansibrightmagenta",
            Token.Name.Entity: "bold ansigray",
            Token.Name.Exception: "bold ansibrightred",
            Token.Name.Function: "ansibrightblue",
            Token.Name.Function.Magic: "",
            Token.Name.Label: "ansibrightyellow",
            Token.Name.Namespace: "bold ansibrightblue",
            Token.Name.Other: "",
            Token.Name.Property: "",
            Token.Name.Tag: "bold ansigreen",
            Token.Name.Variable: "ansiblue",
            Token.Name.Variable.Class: "",
            Token.Name.Variable.Global: "",
            Token.Name.Variable.Instance: "",
            Token.Name.Variable.Magic: "",
            Token.Operator: "ansibrightblack",
            Token.Operator.Word: "bold ansimagenta",
            Token.Other: "",
            Token.Punctuation: "",
            Token.Text: "",
            Token.Text.Whitespace: "ansigray",
            Token.PTK.Aborting: "ansibrightblack",
            Token.PTK.AutoSuggestion: "ansibrightblack",
            Token.PTK.CompletionMenu: "bg:ansigray ansiblack",
            Token.PTK.CompletionMenu.Completion: "",
            Token.PTK.CompletionMenu.Completion.Current: "bg:ansibrightblack ansiwhite",
            Token.PTK.Scrollbar.Arrow: "bg:ansiblack ansiwhite bold",
            Token.PTK.Scrollbar.Background: "bg:ansibrightblack",
            Token.PTK.Scrollbar.Button: "bg:ansiblack",
        },
    ),
    globals(),
    "DEFAULT_STYLE_DICT",
)
