"""Hooks for pygments syntax highlighting."""

import os
import re
import stat
import sys
from collections import ChainMap
from collections.abc import MutableMapping
from keyword import iskeyword

import pygments.util
from pygments.lexer import bygroups, include, inherit
from pygments.lexers.agile import Python3Lexer
from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Token,
    Whitespace,
    _TokenType,
)

from xonsh.built_ins import XSH
from xonsh.color_tools import (
    BASE_XONSH_COLORS,
    RE_BACKGROUND,
    RE_XONSH_COLOR,
    find_closest_color,
    iscolor,
    make_palette,
    warn_deprecated_no_color,
)
from xonsh.events import events
from xonsh.lib.lazyasd import LazyDict, LazyObject, lazyobject
from xonsh.lib.lazyimps import html, os_listxattr, terminal256
from xonsh.platform import (
    os_environ,
    ptk_version_info,
    pygments_version_info,
    win_ansi_support,
)
from xonsh.procs.executables import locate_executable
from xonsh.pygments_cache import add_custom_style, get_style_by_name
from xonsh.style_tools import DEFAULT_STYLE_DICT, norm_name
from xonsh.tools import (
    ANSICOLOR_NAMES_MAP,
    FORMATTER,
    ON_WINDOWS,
    PTK_NEW_OLD_COLOR_MAP,
    hardcode_colors_for_win10,
    intensify_colors_for_cmd_exe,
)

#
# Colors and Styles
#

Color = Token.Color  # alias to new color token namespace

# style rules that are not supported by pygments are stored here
NON_PYGMENTS_RULES: dict[str, dict[str, str]] = {}

# style modifiers not handled by pygments (but supported by ptk)
PTK_SPECIFIC_VALUES = frozenset(
    {"reverse", "noreverse", "hidden", "nohidden", "blink", "noblink"}
)

# Generate fallback style dict from non-pygments styles
# (Let pygments handle the defaults where it can)
FALLBACK_STYLE_DICT = LazyObject(
    lambda: {
        token: value
        for token, value in DEFAULT_STYLE_DICT.items()
        if str(token).startswith("Token.PTK")
    },
    globals(),
    "FALLBACK_STYLE_DICT",
)


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
        return Color.DEFAULT, None, None
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


@lazyobject
def PYGMENTS_MODIFIERS():
    # pygments doesn't support all modifiers.
    # use None to represent unsupported
    return {
        "BOLD": "bold",
        "FAINT": None,
        "ITALIC": "italic",
        "UNDERLINE": "underline",
        "SLOWBLINK": None,
        "FASTBLINK": None,
        "INVERT": None,
        "CONCEAL": None,
        "STRIKETHROUGH": None,
        "BOLDOFF": None,
        "FAINTOFF": None,
        "ITALICOFF": None,
        "UNDERLINEOFF": None,
        "BLINKOFF": None,
        "INVERTOFF": None,
        "REVEALOFF": None,
        "STRIKETHROUGHOFF": None,
    }


def color_name_to_pygments_code(name, styles):
    """Converts a xonsh color name to a pygments color code."""
    token = getattr(Color, norm_name(name))
    if token in styles:
        return styles[token]
    m = RE_XONSH_COLOR.match(name)
    if m is None:
        raise ValueError(f"{name!r} is not a color!")
    parts = m.groupdict()
    # convert regex match into actual pygments colors
    if parts["reset"] is not None:
        if parts["reset"] == "NO_COLOR":
            warn_deprecated_no_color()
        res = "noinherit"
    elif parts["bghex"] is not None:
        res = "bg:#" + parts["bghex"][3:]
    elif parts["background"] is not None:
        color = parts["color"]
        if "#" in color:
            fgcolor = color
        else:
            fgcolor = styles[getattr(Color, color)]
        if fgcolor == "noinherit":
            res = "noinherit"
        else:
            res = f"bg:{fgcolor}"
    else:
        # have regular, non-background color
        mods = parts["modifiers"]
        if mods is None:
            mods = []
        else:
            mods = mods.strip("_").split("_")
            mods = [PYGMENTS_MODIFIERS[mod] for mod in mods]
        mods = list(filter(None, mods))  # remove unsupported entries
        color = parts["color"]
        if "#" in color:
            mods.append(color)
        else:
            mods.append(styles[getattr(Color, color)])
        res = " ".join(mods)
    styles[token] = res
    return res


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
    fg, _, bg = name.upper().replace("HEX", "#").partition("__")
    if fg.startswith("BACKGROUND_") or fg.startswith("BG#"):
        # swap fore & back if needed.
        fg, bg = bg, fg
    # convert names to codes
    if len(fg) == 0 and len(bg) == 0:
        code = "noinherit"
    elif len(fg) == 0:
        code = color_name_to_pygments_code(bg, styles)
    elif len(bg) == 0:
        code = color_name_to_pygments_code(fg, styles)
    else:
        # have both colors
        code = color_name_to_pygments_code(bg, styles)
        code += " "
        code += color_name_to_pygments_code(fg, styles)
    return code


def color_token_by_name(xc: tuple, styles=None) -> _TokenType:
    """Returns (color) token corresponding to Xonsh color tuple, side effect: defines token is defined in styles"""
    if not styles:
        try:
            styles = XSH.shell.shell.styler.styles  # type:ignore
        except AttributeError:
            pass

    tokName = xc[0]
    if styles:
        pc = color_name_to_pygments_code(xc[0], styles)

        if len(xc) > 1:
            pc += " " + color_name_to_pygments_code(xc[1], styles)
            tokName += "__" + xc[1]

    token = getattr(Color, norm_name(tokName))

    if styles and (token not in styles or not styles[token]):
        styles[token] = pc

    return token


def partial_color_tokenize(template):
    """Tokenizes a template string containing colors. Will return a list
    of tuples mapping the token to the string which has that color.
    These sub-strings maybe templates themselves.
    """
    if XSH.shell is not None:
        styles = XSH.shell.shell.styler.styles
    else:
        styles = None
    color = Color.DEFAULT
    try:
        toks, color = _partial_color_tokenize_main(template, styles)
    except Exception:
        toks = [(Color.DEFAULT, template)]
    if styles is not None:
        styles[color]  # ensure color is available
    return toks


def _partial_color_tokenize_main(template, styles):
    bopen = "{"
    bclose = "}"
    colon = ":"
    expl = "!"
    color = Color.DEFAULT
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


class CompoundColorMap(MutableMapping):
    """Looks up color tokens by name, potentially generating the value
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
        pre, _, name = str(key).rpartition(".")
        if pre != "Token.Color":
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

    def __init__(self, style_name="default"):
        """
        Parameters
        ----------
        style_name : str, optional
            The style name to initialize with.
        """
        self.trap = {}  # for trapping custom colors set by user
        self._smap = {}
        self._style_name = ""
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
                print(
                    f"Could not find style {value!r}, using default",
                    file=sys.stderr,
                )
                value = "default"
                XSH.env["XONSH_COLOR_STYLE"] = value
        cmap = STYLES[value]
        if value == "default":
            self._smap = XONSH_BASE_STYLE.copy()
        else:
            try:
                style_obj = get_style_by_name(value)()
                self._smap = style_obj.styles.copy()
                self.highlight_color = style_obj.highlight_color
                self.background_color = style_obj.background_color
            except (ImportError, pygments.util.ClassNotFound):
                self._smap = XONSH_BASE_STYLE.copy()

        compound = CompoundColorMap(
            ChainMap(self.trap, cmap, self._smap, FALLBACK_STYLE_DICT)
        )
        self.styles = ChainMap(
            self.trap, cmap, self._smap, FALLBACK_STYLE_DICT, compound
        )
        self._style_name = value

        for file_type, xonsh_color in XSH.env.get("LS_COLORS", {}).items():
            color_token = color_token_by_name(xonsh_color, self.styles)
            file_color_tokens[file_type] = color_token

        if ON_WINDOWS and "prompt_toolkit" in XSH.shell.shell_type:
            self.enhance_colors_for_cmd_exe()

    @style_name.deleter
    def style_name(self):
        self._style_name = ""

    @property
    def non_pygments_rules(self):
        return NON_PYGMENTS_RULES.get(self.style_name, {})

    def override(self, style_dict):
        self.trap.update(_tokenize_style_dict(style_dict))

    def enhance_colors_for_cmd_exe(self):
        """Enhance colors when using cmd.exe on windows.
        When using the default style all blue and dark red colors
        are changed to CYAN and intense red.
        """
        env = XSH.env
        # Ensure we are not using the new Windows Terminal, ConEmu or Visual Stuio Code
        if "WT_SESSION" in env or "CONEMUANSI" in env or "VSCODE_PID" in env:
            return
        if env.get("INTENSIFY_COLORS_ON_WIN", False):
            if win_ansi_support():
                newcolors = hardcode_colors_for_win10(self.styles)
            else:
                newcolors = intensify_colors_for_cmd_exe(self.styles)
            self.trap.update(newcolors)


def xonsh_style_proxy(styler):
    """Factory for a proxy class to a xonsh style."""
    # Monky patch pygments' list of known ansi colors
    # with the new ansi color names used by PTK2
    # Can be removed once pygment names get fixed.
    if pygments_version_info() and pygments_version_info() < (2, 4, 0):
        pygments.style.ansicolors.update(ANSICOLOR_NAMES_MAP)

    class XonshStyleProxy(Style):
        """Simple proxy class to fool prompt toolkit."""

        target = styler
        styles = styler.styles
        highlight_color = styler.highlight_color
        background_color = styler.background_color

        def __new__(cls, *args, **kwargs):
            return cls.target

    return XonshStyleProxy


def _ptk_specific_style_value(style_value):
    """Checks if the given value is PTK style specific"""
    for ptk_spec in PTK_SPECIFIC_VALUES:
        if ptk_spec in style_value:
            return True

    return False


def _format_ptk_style_name(name):
    """Format PTK style name to be able to include it in a pygments style"""
    parts = name.split("-")
    return "".join(part.capitalize() for part in parts)


def _get_token_by_name(name):
    """Get pygments token object by its string representation."""
    if not isinstance(name, str):
        return name

    token = Token
    parts = name.split(".")

    # PTK - all lowercase
    if parts[0] == parts[0].lower():
        parts = ["PTK"] + [_format_ptk_style_name(part) for part in parts]

    # color name
    if len(parts) == 1:
        return color_token_by_name((name,))

    if parts[0] == "Token":
        parts = parts[1:]

    while len(parts) > 0:
        token = getattr(token, parts[0])
        parts = parts[1:]

    return token


def _tokenize_style_dict(styles):
    """Converts possible string keys in style dicts to Tokens"""
    return {
        _get_token_by_name(token): value
        for token, value in styles.items()
        if not _ptk_specific_style_value(value)
    }


def register_custom_pygments_style(
    name, styles, highlight_color=None, background_color=None, base="default"
):
    """Register custom style.

    Parameters
    ----------
    name : str
        Style name.
    styles : dict
        Token -> style mapping.
    highlight_color : str
        Hightlight color.
    background_color : str
        Background color.
    base : str, optional
        Base style to use as default.

    Returns
    -------
    style : The ``pygments.Style`` subclass created
    """
    base_style = get_style_by_name(base)
    custom_styles = base_style.styles.copy()

    for token, value in _tokenize_style_dict(styles).items():
        custom_styles[token] = value

    non_pygments_rules = {
        token: value
        for token, value in styles.items()
        if _ptk_specific_style_value(value)
    }

    style = type(
        f"Custom{name}Style",
        (Style,),
        {
            "styles": custom_styles,
            "highlight_color": (
                highlight_color
                if highlight_color is not None
                else base_style.highlight_color
            ),
            "background_color": (
                background_color
                if background_color is not None
                else base_style.background_color
            ),
        },
    )

    add_custom_style(name, style)

    cmap = pygments_style_by_name(base).copy()

    # replace colors in color map if found in styles
    for token in cmap.keys():
        if token in custom_styles:
            cmap[token] = custom_styles[token]

    STYLES[name] = cmap
    if len(non_pygments_rules) > 0:
        NON_PYGMENTS_RULES[name] = non_pygments_rules

    return style


XONSH_BASE_STYLE = LazyObject(
    lambda: {
        Whitespace: "ansigray",
        Comment: "underline ansicyan",
        Comment.Preproc: "underline ansiyellow",
        Keyword: "bold ansigreen",
        Keyword.Pseudo: "nobold",
        Keyword.Type: "nobold ansired",
        Operator: "ansibrightblack",
        Operator.Word: "bold ansimagenta",
        Name.Builtin: "ansigreen",
        Name.Function: "ansibrightblue",
        Name.Class: "bold ansibrightblue",
        Name.Namespace: "bold ansibrightblue",
        Name.Exception: "bold ansibrightred",
        Name.Variable: "ansiblue",
        Name.Constant: "ansired",
        Name.Label: "ansibrightyellow",
        Name.Entity: "bold ansigray",
        Name.Attribute: "ansibrightyellow",
        Name.Tag: "bold ansigreen",
        Name.Decorator: "ansibrightmagenta",
        String: "ansibrightred",
        String.Doc: "underline",
        String.Interpol: "bold ansimagenta",
        String.Escape: "bold ansiyellow",
        String.Regex: "ansimagenta",
        String.Symbol: "ansiyellow",
        String.Other: "ansigreen",
        Number: "ansibrightblack",
        Generic.Heading: "bold ansiblue",
        Generic.Subheading: "bold ansimagenta",
        Generic.Deleted: "ansired",
        Generic.Inserted: "ansibrightgreen",
        Generic.Error: "bold ansibrightred",
        Generic.Emph: "underline",
        Generic.Prompt: "bold ansiblue",
        Generic.Output: "ansiblue",
        Generic.Traceback: "ansiblue",
        Error: "ansibrightred",
    },
    globals(),
    "XONSH_BASE_STYLE",
)


def _bw_style():
    style = {
        Color.BLACK: "noinherit",
        Color.BLUE: "noinherit",
        Color.CYAN: "noinherit",
        Color.GREEN: "noinherit",
        Color.INTENSE_BLACK: "noinherit",
        Color.INTENSE_BLUE: "noinherit",
        Color.INTENSE_CYAN: "noinherit",
        Color.INTENSE_GREEN: "noinherit",
        Color.INTENSE_PURPLE: "noinherit",
        Color.INTENSE_RED: "noinherit",
        Color.INTENSE_WHITE: "noinherit",
        Color.INTENSE_YELLOW: "noinherit",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "noinherit",
        Color.RED: "noinherit",
        Color.WHITE: "noinherit",
        Color.YELLOW: "noinherit",
    }
    return style


def _default_style():
    style = {
        Color.BLACK: "ansiblack",
        Color.BLUE: "ansiblue",
        Color.CYAN: "ansicyan",
        Color.GREEN: "ansigreen",
        Color.INTENSE_BLACK: "ansibrightblack",
        Color.INTENSE_BLUE: "ansibrightblue",
        Color.INTENSE_CYAN: "ansibrightcyan",
        Color.INTENSE_GREEN: "ansibrightgreen",
        Color.INTENSE_PURPLE: "ansibrightmagenta",
        Color.INTENSE_RED: "ansibrightred",
        Color.INTENSE_WHITE: "ansiwhite",
        Color.INTENSE_YELLOW: "ansibrightyellow",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "ansimagenta",
        Color.RED: "ansired",
        Color.WHITE: "ansigray",
        Color.YELLOW: "ansiyellow",
    }
    return style


def _monokai_style():
    style = {
        Color.BLACK: "#1e0010",
        Color.BLUE: "#6666ef",
        Color.CYAN: "#66d9ef",
        Color.GREEN: "#2ee22e",
        Color.INTENSE_BLACK: "#5e5e5e",
        Color.INTENSE_BLUE: "#2626d7",
        Color.INTENSE_CYAN: "#2ed9d9",
        Color.INTENSE_GREEN: "#a6e22e",
        Color.INTENSE_PURPLE: "#ae81ff",
        Color.INTENSE_RED: "#f92672",
        Color.INTENSE_WHITE: "#f8f8f2",
        Color.INTENSE_YELLOW: "#e6db74",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#960050",
        Color.RED: "#AF0000",
        Color.WHITE: "#d7d7d7",
        Color.YELLOW: "#e2e22e",
    }
    return style


######################################
#   Auto-generated below this line   #
######################################
def _algol_style():
    style = {
        Color.BLACK: "#666",
        Color.BLUE: "#666",
        Color.CYAN: "#666",
        Color.GREEN: "#666",
        Color.INTENSE_BLACK: "#666",
        Color.INTENSE_BLUE: "#888",
        Color.INTENSE_CYAN: "#888",
        Color.INTENSE_GREEN: "#888",
        Color.INTENSE_PURPLE: "#888",
        Color.INTENSE_RED: "#FF0000",
        Color.INTENSE_WHITE: "#888",
        Color.INTENSE_YELLOW: "#888",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#666",
        Color.RED: "#FF0000",
        Color.WHITE: "#888",
        Color.YELLOW: "#FF0000",
    }
    return style


def _algol_nu_style():
    style = {
        Color.BLACK: "#666",
        Color.BLUE: "#666",
        Color.CYAN: "#666",
        Color.GREEN: "#666",
        Color.INTENSE_BLACK: "#666",
        Color.INTENSE_BLUE: "#888",
        Color.INTENSE_CYAN: "#888",
        Color.INTENSE_GREEN: "#888",
        Color.INTENSE_PURPLE: "#888",
        Color.INTENSE_RED: "#FF0000",
        Color.INTENSE_WHITE: "#888",
        Color.INTENSE_YELLOW: "#888",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#666",
        Color.RED: "#FF0000",
        Color.WHITE: "#888",
        Color.YELLOW: "#FF0000",
    }
    return style


def _autumn_style():
    style = {
        Color.BLACK: "#000080",
        Color.BLUE: "#0000aa",
        Color.CYAN: "#00aaaa",
        Color.GREEN: "#00aa00",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#1e90ff",
        Color.INTENSE_CYAN: "#1e90ff",
        Color.INTENSE_GREEN: "#4c8317",
        Color.INTENSE_PURPLE: "#FAA",
        Color.INTENSE_RED: "#aa5500",
        Color.INTENSE_WHITE: "#bbbbbb",
        Color.INTENSE_YELLOW: "#FAA",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#aa0000",
        Color.WHITE: "#aaaaaa",
        Color.YELLOW: "#aa5500",
    }
    return style


def _borland_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#000080",
        Color.CYAN: "#008080",
        Color.GREEN: "#008800",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#0000FF",
        Color.INTENSE_CYAN: "#ddffdd",
        Color.INTENSE_GREEN: "#888888",
        Color.INTENSE_PURPLE: "#e3d2d2",
        Color.INTENSE_RED: "#FF0000",
        Color.INTENSE_WHITE: "#ffdddd",
        Color.INTENSE_YELLOW: "#e3d2d2",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#aa0000",
        Color.WHITE: "#aaaaaa",
        Color.YELLOW: "#a61717",
    }
    return style


def _colorful_style():
    style = {
        Color.BLACK: "#000",
        Color.BLUE: "#00C",
        Color.CYAN: "#0e84b5",
        Color.GREEN: "#00A000",
        Color.INTENSE_BLACK: "#555",
        Color.INTENSE_BLUE: "#33B",
        Color.INTENSE_CYAN: "#bbbbbb",
        Color.INTENSE_GREEN: "#888",
        Color.INTENSE_PURPLE: "#FAA",
        Color.INTENSE_RED: "#D42",
        Color.INTENSE_WHITE: "#fff0ff",
        Color.INTENSE_YELLOW: "#FAA",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#A00000",
        Color.WHITE: "#bbbbbb",
        Color.YELLOW: "#A60",
    }
    return style


def _emacs_style():
    style = {
        Color.BLACK: "#008000",
        Color.BLUE: "#000080",
        Color.CYAN: "#04D",
        Color.GREEN: "#00A000",
        Color.INTENSE_BLACK: "#666666",
        Color.INTENSE_BLUE: "#04D",
        Color.INTENSE_CYAN: "#bbbbbb",
        Color.INTENSE_GREEN: "#00BB00",
        Color.INTENSE_PURPLE: "#AA22FF",
        Color.INTENSE_RED: "#D2413A",
        Color.INTENSE_WHITE: "#bbbbbb",
        Color.INTENSE_YELLOW: "#bbbbbb",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#A00000",
        Color.WHITE: "#bbbbbb",
        Color.YELLOW: "#BB6622",
    }
    return style


def _friendly_style():
    style = {
        Color.BLACK: "#007020",
        Color.BLUE: "#000080",
        Color.CYAN: "#0e84b5",
        Color.GREEN: "#00A000",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#70a0d0",
        Color.INTENSE_CYAN: "#60add5",
        Color.INTENSE_GREEN: "#40a070",
        Color.INTENSE_PURPLE: "#bb60d5",
        Color.INTENSE_RED: "#d55537",
        Color.INTENSE_WHITE: "#fff0f0",
        Color.INTENSE_YELLOW: "#bbbbbb",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#A00000",
        Color.WHITE: "#bbbbbb",
        Color.YELLOW: "#c65d09",
    }
    return style


def _fruity_style():
    style = {
        Color.BLACK: "#0f140f",
        Color.BLUE: "#0086d2",
        Color.CYAN: "#0086d2",
        Color.GREEN: "#008800",
        Color.INTENSE_BLACK: "#444444",
        Color.INTENSE_BLUE: "#0086f7",
        Color.INTENSE_CYAN: "#0086f7",
        Color.INTENSE_GREEN: "#888888",
        Color.INTENSE_PURPLE: "#ff0086",
        Color.INTENSE_RED: "#fb660a",
        Color.INTENSE_WHITE: "#ffffff",
        Color.INTENSE_YELLOW: "#cdcaa9",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#ff0086",
        Color.RED: "#ff0007",
        Color.WHITE: "#cdcaa9",
        Color.YELLOW: "#fb660a",
    }
    return style


def _igor_style():
    style = {
        Color.BLACK: "#009C00",
        Color.BLUE: "#0000FF",
        Color.CYAN: "#007575",
        Color.GREEN: "#009C00",
        Color.INTENSE_BLACK: "#007575",
        Color.INTENSE_BLUE: "#0000FF",
        Color.INTENSE_CYAN: "#007575",
        Color.INTENSE_GREEN: "#009C00",
        Color.INTENSE_PURPLE: "#CC00A3",
        Color.INTENSE_RED: "#C34E00",
        Color.INTENSE_WHITE: "#CC00A3",
        Color.INTENSE_YELLOW: "#C34E00",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#CC00A3",
        Color.RED: "#C34E00",
        Color.WHITE: "#CC00A3",
        Color.YELLOW: "#C34E00",
    }
    return style


def _lovelace_style():
    style = {
        Color.BLACK: "#444444",
        Color.BLUE: "#2838b0",
        Color.CYAN: "#289870",
        Color.GREEN: "#388038",
        Color.INTENSE_BLACK: "#666666",
        Color.INTENSE_BLUE: "#2838b0",
        Color.INTENSE_CYAN: "#888888",
        Color.INTENSE_GREEN: "#289870",
        Color.INTENSE_PURPLE: "#a848a8",
        Color.INTENSE_RED: "#b83838",
        Color.INTENSE_WHITE: "#888888",
        Color.INTENSE_YELLOW: "#a89028",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#a848a8",
        Color.RED: "#c02828",
        Color.WHITE: "#888888",
        Color.YELLOW: "#b85820",
    }
    return style


def _manni_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#000099",
        Color.CYAN: "#009999",
        Color.GREEN: "#00CC00",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#9999FF",
        Color.INTENSE_CYAN: "#00CCFF",
        Color.INTENSE_GREEN: "#99CC66",
        Color.INTENSE_PURPLE: "#CC00FF",
        Color.INTENSE_RED: "#FF6600",
        Color.INTENSE_WHITE: "#FFCCCC",
        Color.INTENSE_YELLOW: "#FFCC33",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#CC00FF",
        Color.RED: "#AA0000",
        Color.WHITE: "#AAAAAA",
        Color.YELLOW: "#CC3300",
    }
    return style


def _murphy_style():
    style = {
        Color.BLACK: "#000",
        Color.BLUE: "#000080",
        Color.CYAN: "#0e84b5",
        Color.GREEN: "#00A000",
        Color.INTENSE_BLACK: "#555",
        Color.INTENSE_BLUE: "#66f",
        Color.INTENSE_CYAN: "#5ed",
        Color.INTENSE_GREEN: "#5ed",
        Color.INTENSE_PURPLE: "#e9e",
        Color.INTENSE_RED: "#f84",
        Color.INTENSE_WHITE: "#eee",
        Color.INTENSE_YELLOW: "#fc8",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#A00000",
        Color.WHITE: "#bbbbbb",
        Color.YELLOW: "#c65d09",
    }
    return style


def _native_style():
    style = {
        Color.BLACK: "#520000",
        Color.BLUE: "#3677a9",
        Color.CYAN: "#24909d",
        Color.GREEN: "#589819",
        Color.INTENSE_BLACK: "#666666",
        Color.INTENSE_BLUE: "#447fcf",
        Color.INTENSE_CYAN: "#40ffff",
        Color.INTENSE_GREEN: "#6ab825",
        Color.INTENSE_PURPLE: "#e3d2d2",
        Color.INTENSE_RED: "#cd2828",
        Color.INTENSE_WHITE: "#ffffff",
        Color.INTENSE_YELLOW: "#ed9d13",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#666666",
        Color.RED: "#a61717",
        Color.WHITE: "#aaaaaa",
        Color.YELLOW: "#a61717",
    }
    return style


def _paraiso_dark_style():
    style = {
        Color.BLACK: "#776e71",
        Color.BLUE: "#815ba4",
        Color.CYAN: "#06b6ef",
        Color.GREEN: "#48b685",
        Color.INTENSE_BLACK: "#776e71",
        Color.INTENSE_BLUE: "#815ba4",
        Color.INTENSE_CYAN: "#5bc4bf",
        Color.INTENSE_GREEN: "#48b685",
        Color.INTENSE_PURPLE: "#e7e9db",
        Color.INTENSE_RED: "#ef6155",
        Color.INTENSE_WHITE: "#e7e9db",
        Color.INTENSE_YELLOW: "#fec418",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#815ba4",
        Color.RED: "#ef6155",
        Color.WHITE: "#5bc4bf",
        Color.YELLOW: "#f99b15",
    }
    return style


def _paraiso_light_style():
    style = {
        Color.BLACK: "#2f1e2e",
        Color.BLUE: "#2f1e2e",
        Color.CYAN: "#06b6ef",
        Color.GREEN: "#48b685",
        Color.INTENSE_BLACK: "#2f1e2e",
        Color.INTENSE_BLUE: "#815ba4",
        Color.INTENSE_CYAN: "#5bc4bf",
        Color.INTENSE_GREEN: "#48b685",
        Color.INTENSE_PURPLE: "#815ba4",
        Color.INTENSE_RED: "#ef6155",
        Color.INTENSE_WHITE: "#5bc4bf",
        Color.INTENSE_YELLOW: "#fec418",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#815ba4",
        Color.RED: "#2f1e2e",
        Color.WHITE: "#8d8687",
        Color.YELLOW: "#f99b15",
    }
    return style


def _pastie_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#0000DD",
        Color.CYAN: "#0066bb",
        Color.GREEN: "#008800",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#3333bb",
        Color.INTENSE_CYAN: "#ddffdd",
        Color.INTENSE_GREEN: "#22bb22",
        Color.INTENSE_PURPLE: "#e3d2d2",
        Color.INTENSE_RED: "#dd7700",
        Color.INTENSE_WHITE: "#fff0ff",
        Color.INTENSE_YELLOW: "#e3d2d2",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#bb0066",
        Color.RED: "#aa0000",
        Color.WHITE: "#bbbbbb",
        Color.YELLOW: "#aa6600",
    }
    return style


def _perldoc_style():
    style = {
        Color.BLACK: "#000080",
        Color.BLUE: "#000080",
        Color.CYAN: "#1e889b",
        Color.GREEN: "#00aa00",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#B452CD",
        Color.INTENSE_CYAN: "#bbbbbb",
        Color.INTENSE_GREEN: "#228B22",
        Color.INTENSE_PURPLE: "#B452CD",
        Color.INTENSE_RED: "#CD5555",
        Color.INTENSE_WHITE: "#e3d2d2",
        Color.INTENSE_YELLOW: "#e3d2d2",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#8B008B",
        Color.RED: "#aa0000",
        Color.WHITE: "#a7a7a7",
        Color.YELLOW: "#cb6c20",
    }
    return style


def _rrt_style():
    style = {
        Color.BLACK: "#ff0000",
        Color.BLUE: "#87ceeb",
        Color.CYAN: "#87ceeb",
        Color.GREEN: "#00ff00",
        Color.INTENSE_BLACK: "#87ceeb",
        Color.INTENSE_BLUE: "#87ceeb",
        Color.INTENSE_CYAN: "#7fffd4",
        Color.INTENSE_GREEN: "#00ff00",
        Color.INTENSE_PURPLE: "#ee82ee",
        Color.INTENSE_RED: "#ff0000",
        Color.INTENSE_WHITE: "#e5e5e5",
        Color.INTENSE_YELLOW: "#eedd82",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#ee82ee",
        Color.RED: "#ff0000",
        Color.WHITE: "#87ceeb",
        Color.YELLOW: "#ff0000",
    }
    return style


def _tango_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#0000cf",
        Color.CYAN: "#3465a4",
        Color.GREEN: "#00A000",
        Color.INTENSE_BLACK: "#204a87",
        Color.INTENSE_BLUE: "#5c35cc",
        Color.INTENSE_CYAN: "#f8f8f8",
        Color.INTENSE_GREEN: "#4e9a06",
        Color.INTENSE_PURPLE: "#f8f8f8",
        Color.INTENSE_RED: "#ef2929",
        Color.INTENSE_WHITE: "#f8f8f8",
        Color.INTENSE_YELLOW: "#c4a000",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#a40000",
        Color.WHITE: "#f8f8f8",
        Color.YELLOW: "#8f5902",
    }
    return style


def _trac_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#000080",
        Color.CYAN: "#009999",
        Color.GREEN: "#808000",
        Color.INTENSE_BLACK: "#555555",
        Color.INTENSE_BLUE: "#445588",
        Color.INTENSE_CYAN: "#ddffdd",
        Color.INTENSE_GREEN: "#999988",
        Color.INTENSE_PURPLE: "#e3d2d2",
        Color.INTENSE_RED: "#bb8844",
        Color.INTENSE_WHITE: "#ffdddd",
        Color.INTENSE_YELLOW: "#e3d2d2",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#800080",
        Color.RED: "#aa0000",
        Color.WHITE: "#aaaaaa",
        Color.YELLOW: "#808000",
    }
    return style


def _vim_style():
    style = {
        Color.BLACK: "#000080",
        Color.BLUE: "#000080",
        Color.CYAN: "#00cdcd",
        Color.GREEN: "#00cd00",
        Color.INTENSE_BLACK: "#666699",
        Color.INTENSE_BLUE: "#3399cc",
        Color.INTENSE_CYAN: "#00cdcd",
        Color.INTENSE_GREEN: "#00cd00",
        Color.INTENSE_PURPLE: "#cd00cd",
        Color.INTENSE_RED: "#FF0000",
        Color.INTENSE_WHITE: "#cccccc",
        Color.INTENSE_YELLOW: "#cdcd00",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#cd00cd",
        Color.RED: "#cd0000",
        Color.WHITE: "#cccccc",
        Color.YELLOW: "#cd0000",
    }
    return style


def _vs_style():
    style = {
        Color.BLACK: "#008000",
        Color.BLUE: "#0000ff",
        Color.CYAN: "#2b91af",
        Color.GREEN: "#008000",
        Color.INTENSE_BLACK: "#2b91af",
        Color.INTENSE_BLUE: "#2b91af",
        Color.INTENSE_CYAN: "#2b91af",
        Color.INTENSE_GREEN: "#2b91af",
        Color.INTENSE_PURPLE: "#2b91af",
        Color.INTENSE_RED: "#FF0000",
        Color.INTENSE_WHITE: "#2b91af",
        Color.INTENSE_YELLOW: "#2b91af",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#a31515",
        Color.RED: "#a31515",
        Color.WHITE: "#2b91af",
        Color.YELLOW: "#a31515",
    }
    return style


def _xcode_style():
    style = {
        Color.BLACK: "#000000",
        Color.BLUE: "#1C01CE",
        Color.CYAN: "#3F6E75",
        Color.GREEN: "#177500",
        Color.INTENSE_BLACK: "#3F6E75",
        Color.INTENSE_BLUE: "#2300CE",
        Color.INTENSE_CYAN: "#3F6E75",
        Color.INTENSE_GREEN: "#3F6E75",
        Color.INTENSE_PURPLE: "#A90D91",
        Color.INTENSE_RED: "#C41A16",
        Color.INTENSE_WHITE: "#3F6E75",
        Color.INTENSE_YELLOW: "#836C28",
        Color.DEFAULT: "noinherit",
        Color.PURPLE: "#A90D91",
        Color.RED: "#C41A16",
        Color.WHITE: "#3F6E75",
        Color.YELLOW: "#836C28",
    }
    return style


STYLES = LazyDict(
    {
        "algol": _algol_style,
        "algol_nu": _algol_nu_style,
        "autumn": _autumn_style,
        "borland": _borland_style,
        "bw": _bw_style,
        "colorful": _colorful_style,
        "default": _default_style,
        "emacs": _emacs_style,
        "friendly": _friendly_style,
        "fruity": _fruity_style,
        "igor": _igor_style,
        "lovelace": _lovelace_style,
        "manni": _manni_style,
        "monokai": _monokai_style,
        "murphy": _murphy_style,
        "native": _native_style,
        "paraiso-dark": _paraiso_dark_style,
        "paraiso-light": _paraiso_light_style,
        "pastie": _pastie_style,
        "perldoc": _perldoc_style,
        "rrt": _rrt_style,
        "tango": _tango_style,
        "trac": _trac_style,
        "vim": _vim_style,
        "vs": _vs_style,
        "xcode": _xcode_style,
    },
    globals(),
    "STYLES",
)

del (
    _algol_style,
    _algol_nu_style,
    _autumn_style,
    _borland_style,
    _bw_style,
    _colorful_style,
    _default_style,
    _emacs_style,
    _friendly_style,
    _fruity_style,
    _igor_style,
    _lovelace_style,
    _manni_style,
    _monokai_style,
    _murphy_style,
    _native_style,
    _paraiso_dark_style,
    _paraiso_light_style,
    _pastie_style,
    _perldoc_style,
    _rrt_style,
    _tango_style,
    _trac_style,
    _vim_style,
    _vs_style,
    _xcode_style,
)


# dynamic styles
def make_pygments_style(palette):
    """Makes a pygments style based on a color palette."""
    global Color
    style = {Color.DEFAULT: "noinherit"}
    for name, t in BASE_XONSH_COLORS.items():
        color = find_closest_color(t, palette)
        style[getattr(Color, name)] = "#" + color
    return style


def pygments_style_by_name(name):
    """Gets or makes a pygments color style by its name."""
    if name in STYLES:
        return STYLES[name]
    pstyle = get_style_by_name(name)
    palette = make_palette(pstyle.styles.values())
    astyle = make_pygments_style(palette)
    STYLES[name] = astyle
    return astyle


def _monkey_patch_pygments_codes():
    """Monky patch pygments' dict of console codes,
    with new color names
    """
    if pygments_version_info() and pygments_version_info() >= (2, 4, 0):
        return

    import pygments.console

    if "brightblack" in pygments.console.codes:
        # Assume that colors are already fixed in pygments
        # for example when using pygments from source
        return

    if not getattr(pygments.console, "_xonsh_patched", False):
        patched_codes = {}
        for new, old in PTK_NEW_OLD_COLOR_MAP.items():
            if old in pygments.console.codes:
                patched_codes[new[1:]] = pygments.console.codes[old]
        pygments.console.codes.update(patched_codes)
        pygments.console._xonsh_patched = True


#
# Formatter
#


@lazyobject
def XonshTerminal256Formatter():
    if (
        ptk_version_info()
        and ptk_version_info() > (2, 0)
        and pygments_version_info()
        and (2, 2, 0) <= pygments_version_info() < (2, 4, 0)
    ):
        # Monky patch pygments' dict of console codes
        # with the new color names used by PTK2
        # Can be removed once pygment names get fixed.
        _monkey_patch_pygments_codes()

    class XonshTerminal256FormatterProxy(terminal256.Terminal256Formatter):
        """Proxy class for xonsh terminal256 formatting that understands.
        xonsh color tokens.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # just keep the opening token for colors.
            color_names = set(map(str, Color.subtypes))
            for name, (opener, _) in self.style_string.items():
                if name in color_names:
                    self.style_string[name] = (opener, "")
            # special case DEFAULT, because it is special.
            self.style_string["Token.Color.DEFAULT"] = ("\x1b[39m", "")

    return XonshTerminal256FormatterProxy


@lazyobject
def XonshHtmlFormatter():
    from pygments.style import ansicolors

    def colorformat(text):
        if text in ansicolors:
            return text
        if text[0:1] == "#":
            col = text[1:]
            if len(col) == 6:
                return col
            elif len(col) == 3:
                return col[0] * 2 + col[1] * 2 + col[2] * 2
        elif text == "":
            return ""
        elif text.startswith("var") or text.startswith("calc"):
            return text
        raise AssertionError(f"wrong color format {text!r}")

    class XonshHtmlFormatterProxy(html.HtmlFormatter):
        """Proxy class for xonsh HTML formatting that understands.
        xonsh color tokens.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # set up classes for colors
            self._ndefs = dict(self.style)
            for t in Color.subtypes:
                if t not in self.style._styles:
                    self._set_ndef_for_color_token(t)
                classname = str(t)[5:].replace(".", "").lower()
                self.ttype2class[t] = classname
                self.class2style[classname] = self._get_color_token_style(t)
            del self._ndefs

        def _get_color_token_style(self, ttype):
            webify = html.webify
            ndef = self._ndefs[ttype]
            style = ""
            if ndef["color"]:
                style += "color: {}; ".format(webify(ndef["color"]))
            if ndef["bold"]:
                style += "font-weight: bold; "
            if ndef["italic"]:
                style += "font-style: italic; "
            if ndef["underline"]:
                style += "text-decoration: underline; "
            if ndef["bgcolor"]:
                style += "background-color: {}; ".format(webify(ndef["bgcolor"]))
            if ndef["border"]:
                style += "border: 1px solid {}; ".format(webify(ndef["border"]))
            return (style[:-2], ttype, len(ttype))

        def _set_ndef_for_color_token(self, ttype):
            ndef = self.style._styles.get(ttype.parent, None)
            styledefs = self.style.styles.get(ttype, "").split()
            if not ndef or ttype is None:
                ndef = ["", 0, 0, 0, "", "", 0, 0, 0]
            elif "noinherit" in styledefs and ttype is not Token:
                ndef = self.style._styles[Token][:]
            else:
                ndef = ndef[:]
            self.style._styles[ttype] = ndef
            for styledef in self.style.styles.get(ttype, "").split():
                if styledef == "noinherit":
                    pass
                elif styledef == "bold":
                    ndef[1] = 1
                elif styledef == "nobold":
                    ndef[1] = 0
                elif styledef == "italic":
                    ndef[2] = 1
                elif styledef == "noitalic":
                    ndef[2] = 0
                elif styledef == "underline":
                    ndef[3] = 1
                elif styledef == "nounderline":
                    ndef[3] = 0
                elif styledef[:3] == "bg:":
                    ndef[4] = colorformat(styledef[3:])
                elif styledef[:7] == "border:":
                    ndef[5] = colorformat(styledef[7:])
                elif styledef == "roman":
                    ndef[6] = 1
                elif styledef == "sans":
                    ndef[7] = 1
                elif styledef == "mono":
                    ndef[8] = 1
                else:
                    ndef[0] = colorformat(styledef)
            self._ndefs[ttype] = self.style.style_for_token(ttype)

    return XonshHtmlFormatterProxy


color_file_extension_RE = LazyObject(
    lambda: re.compile(r".*(\.\w+)$"), globals(), "color_file_extension_RE"
)


file_color_tokens = dict()  # type:ignore
"""Parallel to LS_COLORS, keyed by dircolors keys, but value is a Color token.
Initialized by XonshStyle."""


# define as external funcition so tests can reference it too.
def on_lscolors_change(key, oldvalue, newvalue, **kwargs):
    """if LS_COLORS updated, update file_color_tokens and  corresponding color token in style"""
    if newvalue is None:
        del file_color_tokens[key]
    else:
        file_color_tokens[key] = color_token_by_name(newvalue)


events.on_lscolors_change(on_lscolors_change)


def color_file(file_path: str, path_stat: os.stat_result) -> tuple[_TokenType, str]:
    """Determine color to use for file *approximately* as ls --color would,
       given lstat() results and its path.

    Parameters
    ----------
    file_path
        relative path of file (as user typed it).
    path_stat
        lstat() results for file_path.

    Returns
    -------
    color token, color_key

    Notes
    -----
    * implementation follows one authority:
      https://github.com/coreutils/coreutils/blob/master/src/ls.c#L4879
    * except:

      1. does not return 'mi'.  That's the color ls uses to show the (missing) *target* of a symlink
         (in ls -l, not ls).
      2. in dircolors, setting type code to '0 or '00' bypasses that test and proceeds to others.
         In our implementation, setting code to '00' paints the file with no color.
         This is arguably a bug.
    """

    lsc = XSH.env["LS_COLORS"]  # type:ignore
    color_key = "fi"

    # if symlink, get info on (final) target
    if stat.S_ISLNK(path_stat.st_mode):
        try:
            tar_path_stat = os.stat(file_path)  # and work with its properties
            if lsc.is_target("ln"):  # if ln=target
                path_stat = tar_path_stat
        except FileNotFoundError:  # bug always color broken link 'or'
            color_key = "or"  # early exit
            ret_color_token = file_color_tokens.get(color_key, Text)
            return ret_color_token, color_key

    mode = path_stat.st_mode

    if stat.S_ISREG(mode):
        if mode & stat.S_ISUID:
            color_key = "su"
        elif mode & stat.S_ISGID:
            color_key = "sg"
        else:
            cap = os_listxattr(file_path, follow_symlinks=False)
            if cap and "security.capability" in cap:  # protect None return on some OS?
                color_key = "ca"
            elif stat.S_IMODE(mode) & (stat.S_IXUSR + stat.S_IXGRP + stat.S_IXOTH):
                color_key = "ex"
            elif path_stat.st_nlink > 1:
                color_key = "mh"
            else:
                color_key = "fi"
    elif stat.S_ISDIR(mode):  # ls --color doesn't colorize sticky or ow if not dirs...
        color_key = "di"
        if not (ON_WINDOWS):  # on Windows, these do not mean what you think they mean.
            if (mode & stat.S_ISVTX) and (mode & stat.S_IWOTH):
                color_key = "tw"
            elif mode & stat.S_IWOTH:
                color_key = "ow"
            elif mode & stat.S_ISVTX:
                color_key = "st"
    elif stat.S_ISLNK(mode):
        color_key = "ln"
    elif stat.S_ISFIFO(mode):
        color_key = "pi"
    elif stat.S_ISSOCK(mode):
        color_key = "so"
    elif stat.S_ISBLK(mode):
        color_key = "bd"
    elif stat.S_ISCHR(mode):
        color_key = "cd"
    elif stat.S_ISDOOR(mode):  # type:ignore
        color_key = "do"
    else:
        color_key = "or"  # any other type --> orphan

    # if still normal file -- try color by file extension.
    # note: symlink to *.<ext> will be colored 'fi' unless the symlink itself
    # ends with .<ext>. `ls` does the same.  Bug-for-bug compatibility!
    if color_key == "fi":
        match = color_file_extension_RE.match(file_path)
        if match:
            ext = "*" + match.group(1)  # look for *.<fileExtension> coloring
            if ext in lsc:
                color_key = ext

    ret_color_token = file_color_tokens.get(color_key, Text)

    return ret_color_token, color_key


# pygments hooks.


def _command_is_valid(cmd):
    return (cmd in XSH.aliases or locate_executable(cmd)) and not iskeyword(cmd)


def _command_is_autocd(cmd):
    if not XSH.env.get("AUTO_CD", False):
        return False
    try:
        cmd_abspath = os.path.abspath(os.path.expanduser(cmd))
    except OSError:
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
    yieldVal = Text
    try:
        path = os.path.expanduser(text)
        path_stat = os.lstat(path)  # lstat() will raise FNF if not a real file
        yieldVal, _ = color_file(path, path_stat)
    except OSError:
        pass

    yield (match.start(), yieldVal, text)


COMMAND_TOKEN_RE = r'[^=\s\[\]{}()$"\'`<&|;!]+(?=\s|$|\)|\]|\}|!)'


class XonshLexer(Python3Lexer):
    """Xonsh console lexer for pygments."""

    name = "Xonsh lexer"
    aliases = ["xonsh", "xsh"]
    filenames = ["*.xsh", "*xonshrc"]

    def __init__(self, *args, **kwargs):
        # If the lexer is loaded as a pygment plugin, we have to mock
        # __xonsh__.env
        if getattr(XSH, "env", None) is None:
            XSH.env = {}
            if ON_WINDOWS:
                pathext = os_environ.get("PATHEXT", [".EXE", ".BAT", ".CMD"])
                XSH.env["PATHEXT"] = pathext.split(os.pathsep)
        super().__init__(*args, **kwargs)

    tokens = {
        "mode_switch_brackets": [
            (r"(\$)(\{)", bygroups(Keyword, Punctuation), "py_curly_bracket"),
            (r"(@)(\()", bygroups(Keyword, Punctuation), "py_bracket"),
            (
                r"([\!\$])(\()",
                bygroups(Keyword, Punctuation),
                ("subproc_bracket", "subproc_start"),
            ),
            (
                r"(@\$)(\()",
                bygroups(Keyword, Punctuation),
                ("subproc_bracket", "subproc_start"),
            ),
            (
                r"([\!\$])(\[)",
                bygroups(Keyword, Punctuation),
                ("subproc_square_bracket", "subproc_start"),
            ),
            (r"(g?)(`)", bygroups(String.Affix, String.Backtick), "backtick_re"),
        ],
        "subproc_bracket": [(r"\)", Punctuation, "#pop"), include("subproc")],
        "subproc_square_bracket": [(r"\]", Punctuation, "#pop"), include("subproc")],
        "py_bracket": [(r"\)", Punctuation, "#pop"), include("root")],
        "py_curly_bracket": [(r"\}", Punctuation, "#pop"), include("root")],
        "backtick_re": [
            (r"[\.\^\$\*\+\?\[\]\|]", String.Regex),
            (r"({[0-9]+}|{[0-9]+,[0-9]+})\??", String.Regex),
            (r"\\([0-9]+|[AbBdDsSwWZabfnrtuUvx\\])", String.Escape),
            (r"`", String.Backtick, "#pop"),
            (r"[^`\.\^\$\*\+\?\[\]\|]+", String.Backtick),
        ],
        "root": [
            (r"\?", Keyword),
            (r"(?<=\w)!", Keyword),
            (r"\$\w+", Name.Variable),
            (r"\(", Punctuation, "py_bracket"),
            (r"\{", Punctuation, "py_curly_bracket"),
            include("mode_switch_brackets"),
            inherit,
        ],
        "subproc_start": [
            (r"\s+", Whitespace),
            (COMMAND_TOKEN_RE, subproc_cmd_callback, "#pop"),
            (r"", Whitespace, "#pop"),
        ],
        "subproc": [
            include("mode_switch_brackets"),
            (r"&&|\|\||\band\b|\bor\b", Operator, "subproc_start"),
            (r'"(\\\\|\\[0-7]+|\\.|[^"\\])*"', String.Double),
            (r"'(\\\\|\\[0-7]+|\\.|[^'\\])*'", String.Single),
            (r"(?<=\w|\s)!", Keyword, "subproc_macro"),
            (r"^!", Keyword, "subproc_macro"),
            (r";", Punctuation, "subproc_start"),
            (r"&|=", Punctuation),
            (r"\|", Punctuation, "subproc_start"),
            (r"\s+", Text),
            (r'[^=\s\[\]{}()$"\'`<&|;]+', subproc_arg_callback),
            (r"<", Text),
            (r"\$\w+", Name.Variable),
        ],
        "subproc_macro": [
            (r"(\s*)([^\n]+)", bygroups(Whitespace, String)),
            (r"", Whitespace, "#pop"),
        ],
    }

    def get_tokens_unprocessed(self, text, **_):
        """Check first command, then call super.get_tokens_unprocessed
        with root or subproc state"""
        start = 0
        state = ("root",)
        m = re.match(rf"(\s*)({COMMAND_TOKEN_RE})", text)
        if m is not None:
            yield m.start(1), Whitespace, m.group(1)
            start = m.end(1)
            cmd = m.group(2)
            cmd_is_valid = _command_is_valid(cmd)
            cmd_is_autocd = _command_is_autocd(cmd)

            if cmd_is_valid or cmd_is_autocd:
                yield (m.start(2), Name.Builtin if cmd_is_valid else Name.Constant, cmd)
                start = m.end(2)
                state = ("subproc",)

        for i, t, v in super().get_tokens_unprocessed(text[start:], state):
            yield i + start, t, v


class XonshConsoleLexer(XonshLexer):
    """Xonsh console lexer for pygments."""

    name = "Xonsh console lexer"
    aliases = ["xonshcon"]
    filenames: list[str] = []

    tokens = {
        "root": [
            (r"^(>>>|\.\.\.) ", Generic.Prompt),
            (r"\n(>>>|\.\.\.)", Generic.Prompt),
            (r"\n(?![>.][>.][>.] )([^\n]*)", Generic.Output),
            (r"\n(?![>.][>.][>.] )(.*?)$", Generic.Output),
            inherit,
        ]
    }
