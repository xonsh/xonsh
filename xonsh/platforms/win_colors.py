"""Color helpers for the Windows console host."""

from xonsh.lib.lazyasd import LazyObject

__all__ = ("WIN10_COLOR_MAP", "WIN_BOLD_COLOR_MAP", "hardcode_colors_for_win10")


def _win10_color_map():
    cmap = {
        "ansiblack": (12, 12, 12),
        "ansiblue": (0, 55, 218),
        "ansigreen": (19, 161, 14),
        "ansicyan": (58, 150, 221),
        "ansired": (197, 15, 31),
        "ansimagenta": (136, 23, 152),
        "ansiyellow": (193, 156, 0),
        "ansigray": (204, 204, 204),
        "ansibrightblack": (118, 118, 118),
        "ansibrightblue": (59, 120, 255),
        "ansibrightgreen": (22, 198, 12),
        "ansibrightcyan": (97, 214, 214),
        "ansibrightred": (231, 72, 86),
        "ansibrightmagenta": (180, 0, 158),
        "ansibrightyellow": (249, 241, 165),
        "ansiwhite": (242, 242, 242),
    }
    return {k: f"#{r:02x}{g:02x}{b:02x}" for k, (r, g, b) in cmap.items()}


WIN10_COLOR_MAP = LazyObject(_win10_color_map, globals(), "WIN10_COLOR_MAP")


def _win_bold_color_map():
    """Map dark ANSI colors to their lighter variants."""
    return {
        "ansiblack": "ansibrightblack",
        "ansiblue": "ansibrightblue",
        "ansigreen": "ansibrightgreen",
        "ansicyan": "ansibrightcyan",
        "ansired": "ansibrightred",
        "ansimagenta": "ansibrightmagenta",
        "ansiyellow": "ansibrightyellow",
        "ansigray": "ansiwhite",
    }


WIN_BOLD_COLOR_MAP = LazyObject(_win_bold_color_map, globals(), "WIN_BOLD_COLOR_MAP")


def hardcode_colors_for_win10(style_map):
    """Replace ANSI colors with readable RGB values for ``conhost.exe``."""
    from xonsh.built_ins import XSH

    modified_style = {}
    if not XSH.env["PROMPT_TOOLKIT_COLOR_DEPTH"]:
        XSH.env["PROMPT_TOOLKIT_COLOR_DEPTH"] = "DEPTH_24_BIT"
    for token, style_str in style_map.items():
        for ansicolor in WIN10_COLOR_MAP:
            if ansicolor in style_str:
                if "bold" in style_str and "nobold" not in style_str:
                    # Win10 does not handle bold colors. Map dark colors to
                    # their lighter variants to simulate the same effect.
                    style_str = style_str.replace("bold", "")
                    hexcolor = WIN10_COLOR_MAP[
                        WIN_BOLD_COLOR_MAP.get(ansicolor, ansicolor)
                    ]
                else:
                    hexcolor = WIN10_COLOR_MAP[ansicolor]
                style_str = style_str.replace(ansicolor, hexcolor)
        modified_style[token] = style_str
    return modified_style
