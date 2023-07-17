"""Tools for helping with ANSI color codes."""
import re
import sys
import warnings

from xonsh.built_ins import XSH
from xonsh.color_tools import (
    BASE_XONSH_COLORS,
    RE_XONSH_COLOR,
    find_closest_color,
    iscolor,
    make_palette,
    rgb2short,
    rgb_to_256,
    short_to_ints,
    warn_deprecated_no_color,
)
from xonsh.lazyasd import LazyDict, lazyobject
from xonsh.platform import HAS_PYGMENTS
from xonsh.tools import FORMATTER

# pygments modifier to ANSI escape code mapping
_PART_STYLE_CODE_MAPPING = {
    "bold": "1",
    "nobold": "21",
    "italic": "3",
    "noitalic": "23",
    "underline": "4",
    "nounderline": "24",
    "blink": "5",
    "noblink": "25",
    "reverse": "7",
    "noreverse": "27",
    "hidden": "8",
    "nohidden": "28",
}


def _ensure_color_map(style="default", cmap=None):
    if cmap is not None:
        pass
    elif style in ANSI_STYLES:
        cmap = ANSI_STYLES[style]
    else:
        try:  # dynamically loading the style
            cmap = ansi_style_by_name(style)
        except Exception:
            msg = "Could not find color style {0!r}, using default."
            print(msg.format(style), file=sys.stderr)
            XSH.env["XONSH_COLOR_STYLE"] = "default"
            cmap = ANSI_STYLES["default"]
    return cmap


@lazyobject
def ANSI_ESCAPE_MODIFIERS():
    return {
        "BOLD": "1",
        "FAINT": "2",
        "ITALIC": "3",
        "UNDERLINE": "4",
        "SLOWBLINK": "5",
        "FASTBLINK": "6",
        "INVERT": "7",
        "CONCEAL": "8",
        "STRIKETHROUGH": "9",
        "BOLDOFF": "21",
        "FAINTOFF": "22",
        "ITALICOFF": "23",
        "UNDERLINEOFF": "24",
        "BLINKOFF": "25",
        "INVERTOFF": "27",
        "REVEALOFF": "28",
        "STRIKETHROUGHOFF": "29",
    }


def ansi_color_name_to_escape_code(name, style="default", cmap=None):
    """Converts a color name to the inner part of an ANSI escape code"""
    cmap = _ensure_color_map(style=style, cmap=cmap)
    if name in cmap:
        return cmap[name]
    m = RE_XONSH_COLOR.match(name)
    if m is None:
        raise ValueError(f"{name!r} is not a color!")
    parts = m.groupdict()
    # convert regex match into actual ANSI colors
    if parts["reset"] is not None:
        if parts["reset"] == "NO_COLOR":
            warn_deprecated_no_color()
        res = "0"
    elif parts["bghex"] is not None:
        res = "48;5;" + rgb_to_256(parts["bghex"][3:])[0]
    elif parts["background"] is not None:
        color = parts["color"]
        if "#" in color:
            res = "48;5;" + rgb_to_256(color[1:])[0]
        else:
            fgcolor = cmap[color]
            if fgcolor.isdecimal():
                res = str(int(fgcolor) + 10)
            elif fgcolor.startswith("38;"):
                res = "4" + fgcolor[1:]
            elif fgcolor == "DEFAULT":
                res = "39"
            else:
                msg = (
                    "when converting {!r}, did not recognize {!r} within "
                    "the following color map as a valid color:\n\n{!r}"
                )
                raise ValueError(msg.format(name, fgcolor, cmap))
    else:
        # have regular, non-background color
        mods = parts["modifiers"]
        if mods is None:
            mods = []
        else:
            mods = mods.strip("_").split("_")
            mods = [ANSI_ESCAPE_MODIFIERS[mod] for mod in mods]
        color = parts["color"]
        if "#" in color:
            mods.append("38;5;" + rgb_to_256(color[1:])[0])
        elif color == "DEFAULT":
            res = "39"
        else:
            mods.append(cmap[color])
        res = ";".join(mods)
    cmap[name] = res
    return res


def ansi_partial_color_format(template, style="default", cmap=None, hide=False):
    """Formats a template string but only with respect to the colors.
    Another template string is returned, with the color values filled in.

    Parameters
    ----------
    template : str
        The template string, potentially with color names.
    style : str, optional
        Style name to look up color map from.
    cmap : dict, optional
        A color map to use, this will prevent the color map from being
        looked up via the style name.
    hide : bool, optional
        Whether to wrap the color codes in the \\001 and \\002 escape
        codes, so that the color codes are not counted against line
        length.

    Returns
    -------
    A template string with the color values filled in.
    """
    try:
        return _ansi_partial_color_format_main(
            template, style=style, cmap=cmap, hide=hide
        )
    except Exception:
        return template


def _ansi_partial_color_format_main(template, style="default", cmap=None, hide=False):
    cmap = _ensure_color_map(style=style, cmap=cmap)
    overrides = XSH.env["XONSH_STYLE_OVERRIDES"]
    if overrides:
        cmap.update(_style_dict_to_ansi(overrides))
    esc = ("\001" if hide else "") + "\033["
    m = "m" + ("\002" if hide else "")
    bopen = "{"
    bclose = "}"
    colon = ":"
    expl = "!"
    toks = []
    for literal, field, spec, conv in FORMATTER.parse(template):
        toks.append(literal)
        if field is None:
            pass
        elif field in cmap:
            toks.extend([esc, cmap[field], m])
        elif iscolor(field):
            color = ansi_color_name_to_escape_code(field, cmap=cmap)
            cmap[field] = color
            toks.extend([esc, color, m])
        elif field is not None:
            toks.append(bopen)
            toks.append(field)
            if conv is not None and len(conv) > 0:
                toks.append(expl)
                toks.append(conv)
            if spec is not None and len(spec) > 0:
                toks.append(colon)
                toks.append(spec)
            toks.append(bclose)
    return "".join(toks)


def ansi_color_style_names():
    """Returns an iterable of all ANSI color style names."""
    return ANSI_STYLES.keys()


def ansi_color_style(style="default"):
    """Returns the current color map."""
    if style in ANSI_STYLES:
        cmap = ANSI_STYLES[style]
    else:
        msg = f"Could not find color style {style!r}, using default."
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        cmap = ANSI_STYLES["default"]
    return cmap


def ansi_reverse_style(style="default", return_style=False):
    """Reverses an ANSI color style mapping so that escape codes map to
    colors. Style may either be string or mapping. May also return
    the style it looked up.
    """
    style = ansi_style_by_name(style) if isinstance(style, str) else style
    reversed_style = {v: k for k, v in style.items()}
    # add keys to make this more useful
    updates = {
        "1": "BOLD_",
        "2": "FAINT_",
        "3": "ITALIC_",
        "4": "UNDERLINE_",
        "5": "SLOWBLINK_",
        "6": "FASTBLINK_",
        "7": "INVERT_",
        "8": "CONCEAL_",
        "9": "STRIKETHROUGH_",
        "21": "BOLDOFF_",
        "22": "FAINTOFF_",
        "23": "ITALICOFF_",
        "24": "UNDERLINEOFF_",
        "25": "BLINKOFF_",
        "27": "INVERTOFF_",
        "28": "REVEALOFF_",
        "29": "STRIKETHROUGHOFF_",
        "38": "SET_FOREGROUND_",
        "48": "SET_BACKGROUND_",
        "38;2": "SET_FOREGROUND_FAINT_",
        "48;2": "SET_BACKGROUND_FAINT_",
        "38;5": "SET_FOREGROUND_SLOWBLINK_",
        "48;5": "SET_BACKGROUND_SLOWBLINK_",
    }
    for ec, name in reversed_style.items():
        no_left_zero = ec.lstrip("0")
        if no_left_zero.startswith(";"):
            updates[no_left_zero[1:]] = name
        elif no_left_zero != ec:
            updates[no_left_zero] = name
    reversed_style.update(updates)
    # return results
    if return_style:
        return style, reversed_style
    else:
        return reversed_style


@lazyobject
def ANSI_ESCAPE_CODE_RE():
    return re.compile(r"\001?(\033\[)?([0-9;]+)m?\002?")


@lazyobject
def ANSI_COLOR_NAME_SET_3INTS_RE():
    return re.compile(r"(\w+_)?SET_(FORE|BACK)GROUND_FAINT_(\d+)_(\d+)_(\d+)")


@lazyobject
def ANSI_COLOR_NAME_SET_SHORT_RE():
    return re.compile(r"(\w+_)?SET_(FORE|BACK)GROUND_SLOWBLINK_(\d+)")


def _color_name_from_ints(ints, background=False, prefix=None):
    name = find_closest_color(ints, BASE_XONSH_COLORS)
    if background:
        name = "BACKGROUND_" + name
    name = name if prefix is None else prefix + name
    return name


def ansi_color_escape_code_to_name(escape_code, style, reversed_style=None):
    """Converts an ANSI color code escape sequence to a tuple of color names
    in the provided style ('default' should almost be the style). For example,
    '0' becomes ('RESET',) and '32;41' becomes ('GREEN', 'BACKGROUND_RED').
    The style keyword may either be a string, in which the style is looked up,
    or an actual style dict.  You can also provide a reversed style mapping,
    too, which is just the keys/values of the style dict swapped. If reversed
    style is not provided, it is computed.
    """
    if reversed_style is None:
        style, reversed_style = ansi_reverse_style(style, return_style=True)
    # strip some actual escape codes, if needed.
    match = ANSI_ESCAPE_CODE_RE.match(escape_code)
    if not match:
        msg = f'Invalid ANSI color sequence "{escape_code}", using "RESET" instead.'
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return ("RESET",)
    ec = match.group(2)
    names = []
    n_ints = 0
    seen_set_foreback = False
    for e in ec.split(";"):
        no_left_zero = e.lstrip("0") if len(e) > 1 else e
        if seen_set_foreback and n_ints > 0:
            names.append(e)
            n_ints -= 1
            if n_ints == 0:
                seen_set_foreback = False
            continue
        else:
            names.append(reversed_style.get(no_left_zero, no_left_zero))
        # set the flags for next time
        if "38" == e or "48" == e:
            seen_set_foreback = True
        elif seen_set_foreback and "2" == e:
            n_ints = 3
        elif seen_set_foreback and "5" == e:
            n_ints = 1
    # normalize names
    n = ""
    norm_names = []
    prefixes = ""
    for name in names:
        if name in ("RESET", "NO_COLOR"):
            # skip most '0' entries
            continue
        elif "BACKGROUND_" in name and n:
            prefixes += n
            n = ""
        n = n + name if n else name
        if n.endswith("_"):
            continue
        elif ANSI_COLOR_NAME_SET_SHORT_RE.match(n) is not None:
            pre, fore_back, short = ANSI_COLOR_NAME_SET_SHORT_RE.match(n).groups()
            n = _color_name_from_ints(
                short_to_ints(short), background=(fore_back == "BACK"), prefix=pre
            )
        elif ANSI_COLOR_NAME_SET_3INTS_RE.match(n) is not None:
            pre, fore_back, r, g, b = ANSI_COLOR_NAME_SET_3INTS_RE.match(n).groups()
            n = _color_name_from_ints(
                (int(r), int(g), int(b)), background=(fore_back == "BACK"), prefix=pre
            )
        elif "GROUND_FAINT_" in n:
            # have 1 or 2, but not 3 ints
            n += "_"
            continue
        # error check
        if not iscolor(n):
            msg = (
                "Could not translate ANSI color code {escape_code!r} "
                "into a known color in the palette. Specifically, the {n!r} "
                "portion of {name!r} in {names!r} seems to missing."
            )
            raise ValueError(
                msg.format(escape_code=escape_code, names=names, name=name, n=n)
            )
        norm_names.append(n)
        n = ""
    # check if we have pre- & post-fixes to apply to the last, non-background element
    prefixes += n
    if prefixes.endswith("_"):
        for i in range(-1, -len(norm_names) - 1, -1):
            if "BACKGROUND_" not in norm_names[i]:
                norm_names[i] = prefixes + norm_names[i]
                break
        else:
            # only have background colors, so select WHITE as default color
            norm_names.append(prefixes + "WHITE")
    # return
    if len(norm_names) == 0:
        return ("RESET",)
    else:
        return tuple(norm_names)


def _bw_style():
    style = {
        "RESET": "0",
        "BLACK": "0;30",
        "BLUE": "0;37",
        "CYAN": "0;37",
        "GREEN": "0;37",
        "PURPLE": "0;37",
        "RED": "0;37",
        "WHITE": "0;37",
        "YELLOW": "0;37",
        "BACKGROUND_BLACK": "40",
        "BACKGROUND_RED": "47",
        "BACKGROUND_GREEN": "47",
        "BACKGROUND_YELLOW": "47",
        "BACKGROUND_BLUE": "47",
        "BACKGROUND_PURPLE": "47",
        "BACKGROUND_CYAN": "47",
        "BACKGROUND_WHITE": "47",
        "INTENSE_BLACK": "0;90",
        "INTENSE_BLUE": "0;97",
        "INTENSE_CYAN": "0;97",
        "INTENSE_GREEN": "0;97",
        "INTENSE_PURPLE": "0;97",
        "INTENSE_RED": "0;97",
        "INTENSE_WHITE": "0;97",
        "INTENSE_YELLOW": "0;97",
    }
    return style


def _default_style():
    style = {
        # Reset
        "RESET": "0",  # Text Reset
        # Regular Colors
        "BLACK": "30",  # BLACK
        "RED": "31",  # RED
        "GREEN": "32",  # GREEN
        "YELLOW": "33",  # YELLOW
        "BLUE": "34",  # BLUE
        "PURPLE": "35",  # PURPLE
        "CYAN": "36",  # CYAN
        "WHITE": "37",  # WHITE
        # Background
        "BACKGROUND_BLACK": "40",  # BLACK
        "BACKGROUND_RED": "41",  # RED
        "BACKGROUND_GREEN": "42",  # GREEN
        "BACKGROUND_YELLOW": "43",  # YELLOW
        "BACKGROUND_BLUE": "44",  # BLUE
        "BACKGROUND_PURPLE": "45",  # PURPLE
        "BACKGROUND_CYAN": "46",  # CYAN
        "BACKGROUND_WHITE": "47",  # WHITE
        # High Intensity
        "INTENSE_BLACK": "90",  # BLACK
        "INTENSE_RED": "91",  # RED
        "INTENSE_GREEN": "92",  # GREEN
        "INTENSE_YELLOW": "93",  # YELLOW
        "INTENSE_BLUE": "94",  # BLUE
        "INTENSE_PURPLE": "95",  # PURPLE
        "INTENSE_CYAN": "96",  # CYAN
        "INTENSE_WHITE": "97",  # WHITE
        # High Intensity backgrounds
        "BACKGROUND_INTENSE_BLACK": "100",  # BLACK
        "BACKGROUND_INTENSE_RED": "101",  # RED
        "BACKGROUND_INTENSE_GREEN": "102",  # GREEN
        "BACKGROUND_INTENSE_YELLOW": "103",  # YELLOW
        "BACKGROUND_INTENSE_BLUE": "104",  # BLUE
        "BACKGROUND_INTENSE_PURPLE": "105",  # PURPLE
        "BACKGROUND_INTENSE_CYAN": "106",  # CYAN
        "BACKGROUND_INTENSE_WHITE": "107",  # WHITE
    }
    return style


def _monokai_style():
    style = {
        "RESET": "0",
        "BLACK": "38;5;16",
        "BLUE": "38;5;63",
        "CYAN": "38;5;81",
        "GREEN": "38;5;40",
        "PURPLE": "38;5;89",
        "RED": "38;5;124",
        "WHITE": "38;5;188",
        "YELLOW": "38;5;184",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;20",
        "INTENSE_CYAN": "38;5;44",
        "INTENSE_GREEN": "38;5;148",
        "INTENSE_PURPLE": "38;5;141",
        "INTENSE_RED": "38;5;197",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;186",
    }
    return style


####################################
# Auto-generated below this line   #
####################################


def _algol_style():
    style = {
        "BLACK": "38;5;59",
        "BLUE": "38;5;59",
        "CYAN": "38;5;59",
        "GREEN": "38;5;59",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;102",
        "INTENSE_CYAN": "38;5;102",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;102",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;102",
        "INTENSE_YELLOW": "38;5;102",
        "RESET": "0",
        "PURPLE": "38;5;59",
        "RED": "38;5;09",
        "WHITE": "38;5;102",
        "YELLOW": "38;5;09",
    }
    return style


def _algol_nu_style():
    style = {
        "BLACK": "38;5;59",
        "BLUE": "38;5;59",
        "CYAN": "38;5;59",
        "GREEN": "38;5;59",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;102",
        "INTENSE_CYAN": "38;5;102",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;102",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;102",
        "INTENSE_YELLOW": "38;5;102",
        "RESET": "0",
        "PURPLE": "38;5;59",
        "RED": "38;5;09",
        "WHITE": "38;5;102",
        "YELLOW": "38;5;09",
    }
    return style


def _autumn_style():
    style = {
        "BLACK": "38;5;18",
        "BLUE": "38;5;19",
        "CYAN": "38;5;37",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;33",
        "INTENSE_CYAN": "38;5;33",
        "INTENSE_GREEN": "38;5;64",
        "INTENSE_PURPLE": "38;5;217",
        "INTENSE_RED": "38;5;130",
        "INTENSE_WHITE": "38;5;145",
        "INTENSE_YELLOW": "38;5;217",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;130",
    }
    return style


def _borland_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;18",
        "CYAN": "38;5;30",
        "GREEN": "38;5;28",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;21",
        "INTENSE_CYAN": "38;5;194",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;188",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;224",
        "INTENSE_YELLOW": "38;5;188",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;124",
    }
    return style


def _colorful_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;20",
        "CYAN": "38;5;31",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;61",
        "INTENSE_CYAN": "38;5;145",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;217",
        "INTENSE_RED": "38;5;166",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;217",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;130",
    }
    return style


def _emacs_style():
    style = {
        "BLACK": "38;5;28",
        "BLUE": "38;5;18",
        "CYAN": "38;5;26",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;26",
        "INTENSE_CYAN": "38;5;145",
        "INTENSE_GREEN": "38;5;34",
        "INTENSE_PURPLE": "38;5;129",
        "INTENSE_RED": "38;5;167",
        "INTENSE_WHITE": "38;5;145",
        "INTENSE_YELLOW": "38;5;145",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;130",
    }
    return style


def _friendly_style():
    style = {
        "BLACK": "38;5;22",
        "BLUE": "38;5;18",
        "CYAN": "38;5;31",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;74",
        "INTENSE_CYAN": "38;5;74",
        "INTENSE_GREEN": "38;5;71",
        "INTENSE_PURPLE": "38;5;134",
        "INTENSE_RED": "38;5;167",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;145",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;166",
    }
    return style


def _fruity_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;32",
        "CYAN": "38;5;32",
        "GREEN": "38;5;28",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;33",
        "INTENSE_CYAN": "38;5;33",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;198",
        "INTENSE_RED": "38;5;202",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;187",
        "RESET": "0",
        "PURPLE": "38;5;198",
        "RED": "38;5;09",
        "WHITE": "38;5;187",
        "YELLOW": "38;5;202",
    }
    return style


def _igor_style():
    style = {
        "BLACK": "38;5;34",
        "BLUE": "38;5;21",
        "CYAN": "38;5;30",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;30",
        "INTENSE_BLUE": "38;5;21",
        "INTENSE_CYAN": "38;5;30",
        "INTENSE_GREEN": "38;5;34",
        "INTENSE_PURPLE": "38;5;163",
        "INTENSE_RED": "38;5;166",
        "INTENSE_WHITE": "38;5;163",
        "INTENSE_YELLOW": "38;5;166",
        "RESET": "0",
        "PURPLE": "38;5;163",
        "RED": "38;5;166",
        "WHITE": "38;5;163",
        "YELLOW": "38;5;166",
    }
    return style


def _lovelace_style():
    style = {
        "BLACK": "38;5;59",
        "BLUE": "38;5;25",
        "CYAN": "38;5;29",
        "GREEN": "38;5;65",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;25",
        "INTENSE_CYAN": "38;5;102",
        "INTENSE_GREEN": "38;5;29",
        "INTENSE_PURPLE": "38;5;133",
        "INTENSE_RED": "38;5;131",
        "INTENSE_WHITE": "38;5;102",
        "INTENSE_YELLOW": "38;5;136",
        "RESET": "0",
        "PURPLE": "38;5;133",
        "RED": "38;5;124",
        "WHITE": "38;5;102",
        "YELLOW": "38;5;130",
    }
    return style


def _manni_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;18",
        "CYAN": "38;5;30",
        "GREEN": "38;5;40",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;105",
        "INTENSE_CYAN": "38;5;45",
        "INTENSE_GREEN": "38;5;113",
        "INTENSE_PURPLE": "38;5;165",
        "INTENSE_RED": "38;5;202",
        "INTENSE_WHITE": "38;5;224",
        "INTENSE_YELLOW": "38;5;221",
        "RESET": "0",
        "PURPLE": "38;5;165",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;166",
    }
    return style


def _murphy_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;18",
        "CYAN": "38;5;31",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;63",
        "INTENSE_CYAN": "38;5;86",
        "INTENSE_GREEN": "38;5;86",
        "INTENSE_PURPLE": "38;5;213",
        "INTENSE_RED": "38;5;209",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;222",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;166",
    }
    return style


def _native_style():
    style = {
        "BLACK": "38;5;52",
        "BLUE": "38;5;67",
        "CYAN": "38;5;31",
        "GREEN": "38;5;64",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;68",
        "INTENSE_CYAN": "38;5;87",
        "INTENSE_GREEN": "38;5;70",
        "INTENSE_PURPLE": "38;5;188",
        "INTENSE_RED": "38;5;160",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;214",
        "RESET": "0",
        "PURPLE": "38;5;59",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;124",
    }
    return style


def _paraiso_dark_style():
    style = {
        "BLACK": "38;5;95",
        "BLUE": "38;5;97",
        "CYAN": "38;5;39",
        "GREEN": "38;5;72",
        "INTENSE_BLACK": "38;5;95",
        "INTENSE_BLUE": "38;5;97",
        "INTENSE_CYAN": "38;5;79",
        "INTENSE_GREEN": "38;5;72",
        "INTENSE_PURPLE": "38;5;188",
        "INTENSE_RED": "38;5;203",
        "INTENSE_WHITE": "38;5;188",
        "INTENSE_YELLOW": "38;5;220",
        "RESET": "0",
        "PURPLE": "38;5;97",
        "RED": "38;5;203",
        "WHITE": "38;5;79",
        "YELLOW": "38;5;214",
    }
    return style


def _paraiso_light_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;16",
        "CYAN": "38;5;39",
        "GREEN": "38;5;72",
        "INTENSE_BLACK": "38;5;16",
        "INTENSE_BLUE": "38;5;97",
        "INTENSE_CYAN": "38;5;79",
        "INTENSE_GREEN": "38;5;72",
        "INTENSE_PURPLE": "38;5;97",
        "INTENSE_RED": "38;5;203",
        "INTENSE_WHITE": "38;5;79",
        "INTENSE_YELLOW": "38;5;220",
        "RESET": "0",
        "PURPLE": "38;5;97",
        "RED": "38;5;16",
        "WHITE": "38;5;102",
        "YELLOW": "38;5;214",
    }
    return style


def _pastie_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;20",
        "CYAN": "38;5;25",
        "GREEN": "38;5;28",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;61",
        "INTENSE_CYAN": "38;5;194",
        "INTENSE_GREEN": "38;5;34",
        "INTENSE_PURPLE": "38;5;188",
        "INTENSE_RED": "38;5;172",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;188",
        "RESET": "0",
        "PURPLE": "38;5;125",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;130",
    }
    return style


def _perldoc_style():
    style = {
        "BLACK": "38;5;18",
        "BLUE": "38;5;18",
        "CYAN": "38;5;31",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;134",
        "INTENSE_CYAN": "38;5;145",
        "INTENSE_GREEN": "38;5;28",
        "INTENSE_PURPLE": "38;5;134",
        "INTENSE_RED": "38;5;167",
        "INTENSE_WHITE": "38;5;188",
        "INTENSE_YELLOW": "38;5;188",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;166",
    }
    return style


def _rrt_style():
    style = {
        "BLACK": "38;5;09",
        "BLUE": "38;5;117",
        "CYAN": "38;5;117",
        "GREEN": "38;5;46",
        "INTENSE_BLACK": "38;5;117",
        "INTENSE_BLUE": "38;5;117",
        "INTENSE_CYAN": "38;5;122",
        "INTENSE_GREEN": "38;5;46",
        "INTENSE_PURPLE": "38;5;213",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;188",
        "INTENSE_YELLOW": "38;5;222",
        "RESET": "0",
        "PURPLE": "38;5;213",
        "RED": "38;5;09",
        "WHITE": "38;5;117",
        "YELLOW": "38;5;09",
    }
    return style


def _tango_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;20",
        "CYAN": "38;5;61",
        "GREEN": "38;5;34",
        "INTENSE_BLACK": "38;5;24",
        "INTENSE_BLUE": "38;5;62",
        "INTENSE_CYAN": "38;5;15",
        "INTENSE_GREEN": "38;5;64",
        "INTENSE_PURPLE": "38;5;15",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;15",
        "INTENSE_YELLOW": "38;5;178",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;15",
        "YELLOW": "38;5;94",
    }
    return style


def _trac_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;18",
        "CYAN": "38;5;30",
        "GREEN": "38;5;100",
        "INTENSE_BLACK": "38;5;59",
        "INTENSE_BLUE": "38;5;60",
        "INTENSE_CYAN": "38;5;194",
        "INTENSE_GREEN": "38;5;102",
        "INTENSE_PURPLE": "38;5;188",
        "INTENSE_RED": "38;5;137",
        "INTENSE_WHITE": "38;5;224",
        "INTENSE_YELLOW": "38;5;188",
        "RESET": "0",
        "PURPLE": "38;5;90",
        "RED": "38;5;124",
        "WHITE": "38;5;145",
        "YELLOW": "38;5;100",
    }
    return style


def _vim_style():
    style = {
        "BLACK": "38;5;18",
        "BLUE": "38;5;18",
        "CYAN": "38;5;44",
        "GREEN": "38;5;40",
        "INTENSE_BLACK": "38;5;60",
        "INTENSE_BLUE": "38;5;68",
        "INTENSE_CYAN": "38;5;44",
        "INTENSE_GREEN": "38;5;40",
        "INTENSE_PURPLE": "38;5;164",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;188",
        "INTENSE_YELLOW": "38;5;184",
        "RESET": "0",
        "PURPLE": "38;5;164",
        "RED": "38;5;160",
        "WHITE": "38;5;188",
        "YELLOW": "38;5;160",
    }
    return style


def _vs_style():
    style = {
        "BLACK": "38;5;28",
        "BLUE": "38;5;21",
        "CYAN": "38;5;31",
        "GREEN": "38;5;28",
        "INTENSE_BLACK": "38;5;31",
        "INTENSE_BLUE": "38;5;31",
        "INTENSE_CYAN": "38;5;31",
        "INTENSE_GREEN": "38;5;31",
        "INTENSE_PURPLE": "38;5;31",
        "INTENSE_RED": "38;5;09",
        "INTENSE_WHITE": "38;5;31",
        "INTENSE_YELLOW": "38;5;31",
        "RESET": "0",
        "PURPLE": "38;5;124",
        "RED": "38;5;124",
        "WHITE": "38;5;31",
        "YELLOW": "38;5;124",
    }
    return style


def _xcode_style():
    style = {
        "BLACK": "38;5;16",
        "BLUE": "38;5;20",
        "CYAN": "38;5;60",
        "GREEN": "38;5;28",
        "INTENSE_BLACK": "38;5;60",
        "INTENSE_BLUE": "38;5;20",
        "INTENSE_CYAN": "38;5;60",
        "INTENSE_GREEN": "38;5;60",
        "INTENSE_PURPLE": "38;5;126",
        "INTENSE_RED": "38;5;160",
        "INTENSE_WHITE": "38;5;60",
        "INTENSE_YELLOW": "38;5;94",
        "RESET": "0",
        "PURPLE": "38;5;126",
        "RED": "38;5;160",
        "WHITE": "38;5;60",
        "YELLOW": "38;5;94",
    }
    return style


ANSI_STYLES = LazyDict(
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
    "ANSI_STYLES",
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


#
# Dynamically generated styles
#
def make_ansi_style(palette):
    """Makes an ANSI color style from a color palette"""
    style = {"RESET": "0"}
    for name, t in BASE_XONSH_COLORS.items():
        closest = find_closest_color(t, palette)
        if len(closest) == 3:
            closest = "".join([a * 2 for a in closest])
        short = rgb2short(closest)[0]
        style[name] = "38;5;" + short
    return style


def _pygments_to_ansi_style(style):
    """Tries to convert the given pygments style to ANSI style.

    Parameters
    ----------
    style : pygments style value

    Returns
    -------
    ANSI style
    """
    ansi_style_list = []
    parts = style.split(" ")
    for part in parts:
        if part in _PART_STYLE_CODE_MAPPING:
            ansi_style_list.append(_PART_STYLE_CODE_MAPPING[part])
        elif part[:3] == "bg:":
            ansi_style_list.append("48;5;" + rgb2short(part[3:])[0])
        else:
            ansi_style_list.append("38;5;" + rgb2short(part)[0])

    return ";".join(ansi_style_list)


def _style_dict_to_ansi(styles):
    """Converts pygments like style dict to ANSI rules"""
    ansi_style = {}
    for token, style in styles.items():
        token = str(token)  # convert pygments token to str
        parts = token.split(".")
        if len(parts) == 1 or parts[-2] == "Color":
            ansi_style[parts[-1]] = _pygments_to_ansi_style(style)

    return ansi_style


def register_custom_ansi_style(name, styles, base="default"):
    """Register custom ANSI style.

    Parameters
    ----------
    name : str
        Style name.
    styles : dict
        Token (or str) -> style mapping.
    base : str, optional
        Base style to use as default.
    """
    base_style = ANSI_STYLES[base].copy()

    base_style.update(_style_dict_to_ansi(styles))

    ANSI_STYLES[name] = base_style


def ansi_style_by_name(name):
    """Gets or makes an ANSI color style by name. If the styles does not
    exist, it will look for a style using the pygments name.
    """
    if name in ANSI_STYLES:
        return ANSI_STYLES[name]
    elif not HAS_PYGMENTS:
        print(f"could not find style {name!r}, using 'default'")
        return ANSI_STYLES["default"]
    from pygments.util import ClassNotFound

    from xonsh.pygments_cache import get_style_by_name

    try:
        pstyle = get_style_by_name(name)
    except (ModuleNotFoundError, ClassNotFound):
        pstyle = get_style_by_name("default")
    palette = make_palette(pstyle.styles.values())
    astyle = make_ansi_style(palette)
    ANSI_STYLES[name] = astyle
    return astyle
