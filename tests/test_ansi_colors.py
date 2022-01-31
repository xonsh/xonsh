"""Tests ANSI color tools."""
import pytest

from xonsh.ansi_colors import (
    ansi_color_escape_code_to_name,
    ansi_color_name_to_escape_code,
    ansi_color_style_names,
    ansi_reverse_style,
    ansi_style_by_name,
    register_custom_ansi_style,
)

DEFAULT_CMAP = {
    # Reset
    "RESET": "0",  # Text Reset
    # Regular Colors
    "BLACK": "0;30",  # BLACK
    "RED": "0;31",  # RED
    "GREEN": "0;32",  # GREEN
    "YELLOW": "0;33",  # YELLOW
    "BLUE": "0;34",  # BLUE
    "PURPLE": "0;35",  # PURPLE
    "CYAN": "0;36",  # CYAN
    "WHITE": "0;37",  # WHITE
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
}


@pytest.mark.parametrize(
    "name, exp",
    [
        ("RESET", "0"),
        ("RED", "0;31"),
        ("BACKGROUND_RED", "41"),
        ("BACKGROUND_INTENSE_RED", "101"),
        ("BOLD_RED", "1;0;31"),
        ("UNDERLINE_RED", "4;0;31"),
        ("BOLD_UNDERLINE_RED", "1;4;0;31"),
        ("UNDERLINE_BOLD_RED", "4;1;0;31"),
        ("ITALIC_REVEALOFF_WHITE", "3;28;0;37"),
        # The hex code #000 can map to ANSI-256 0 or 16
        ("#000", {"38;5;0", "38;5;16"}),
        ("#000000", {"38;5;0", "38;5;16"}),
        ("BACKGROUND_#000", {"48;5;0", "48;5;16"}),
        ("BACKGROUND_#000000", {"48;5;0", "48;5;16"}),
        ("BG#000", {"48;5;0", "48;5;16"}),
        ("bg#000000", {"48;5;0", "48;5;16"}),
    ],
)
def test_ansi_color_name_to_escape_code_default(name, exp):
    cmap = DEFAULT_CMAP.copy()
    obs = ansi_color_name_to_escape_code(name, cmap=cmap)
    assert obs in exp


RS = ansi_reverse_style(style="default")


@pytest.mark.parametrize("key, value", [("", "RESET"), ("31", "RED")])
def test_ansi_reverse_style(key, value):
    assert key in RS
    assert RS[key] == value


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("0", ("RESET",)),
        ("1", ("BOLD_WHITE",)),
        ("\0010\002", ("RESET",)),
        ("\033[0m", ("RESET",)),
        ("\001\033[0m\002", ("RESET",)),
        ("00;36", ("CYAN",)),
        ("01;31", ("BOLD_RED",)),
        ("04;31", ("UNDERLINE_RED",)),
        ("3;28", ("ITALIC_REVEALOFF_WHITE",)),
        ("1;4;31", ("BOLD_UNDERLINE_RED",)),
        ("4;1;31", ("UNDERLINE_BOLD_RED",)),
        ("31;42", ("RED", "BACKGROUND_GREEN")),
        ("42;31", ("BACKGROUND_GREEN", "RED")),
        ("40", ("BACKGROUND_BLACK",)),
        ("38;5;89", ("PURPLE",)),
        ("48;5;89", ("BACKGROUND_PURPLE",)),
        ("38;2;170;0;0", ("RED",)),
        ("48;2;170;0;0", ("BACKGROUND_RED",)),
        ("1;38;5;124", ("BOLD_RED",)),
        ("4;1;38;2;170;0;0", ("UNDERLINE_BOLD_RED",)),
        ("1;38;5;40", ("BOLD_GREEN",)),
        ("48;5;16;38;5;184", ("BACKGROUND_BLACK", "INTENSE_YELLOW")),
        ("01;05;37;41", ("BOLD_SLOWBLINK_WHITE", "BACKGROUND_RED")),
        ("38;5;113;1", ("BOLD_INTENSE_GREEN",)),
        ("48;5;196;38;5;232;1", ("BACKGROUND_RED", "BOLD_BLACK")),
        ("48;5;3;38;5;0", ("BACKGROUND_YELLOW", "BLACK")),
        (
            "38;5;220;1;3;100",
            ("BOLD_ITALIC_INTENSE_YELLOW", "BACKGROUND_INTENSE_BLACK"),
        ),
        (
            "38;5;220;1;3;100;1",
            ("BOLD_ITALIC_BOLD_INTENSE_YELLOW", "BACKGROUND_INTENSE_BLACK"),
        ),
        ("48;5;235;38;5;139;3", ("BACKGROUND_BLACK", "ITALIC_WHITE")),
        ("38;5;111;4", ("UNDERLINE_WHITE",)),
        ("1;48;5;124", ("BACKGROUND_RED", "BOLD_WHITE")),
        ("5;48;5;124", ("BACKGROUND_RED", "SLOWBLINK_WHITE")),
        ("1;5;38;5;145;48;5;124", ("BOLD_SLOWBLINK_WHITE", "BACKGROUND_RED")),
    ],
)
def test_ansi_color_escape_code_to_name(inp, exp):
    obs = ansi_color_escape_code_to_name(inp, "default", reversed_style=RS)
    assert obs == exp


@pytest.mark.parametrize(
    "color, style",
    [
        (color, style)
        for color in DEFAULT_CMAP.keys()
        for style in ansi_color_style_names()
    ],
)
def test_ansi_color_name_to_escape_code_for_all_styles(color, style):
    escape_code = ansi_color_name_to_escape_code(color, style)
    assert len(escape_code) > 0


@pytest.mark.parametrize(
    "style_name",
    [
        ("default"),
        ("monokai"),  # defined in `ansi_colors.py`
        ("rainbow_dash"),  # not in `ansi_colors.py`, but in pygments
        ("foobar"),  # invalid, should not fail
    ],
)
def test_ansi_style_by_name(style_name):
    style = ansi_style_by_name(style_name)
    assert style is not None


@pytest.mark.parametrize(
    "name, styles, refrules",
    [
        ("test1", {}, {}),
        ("test2", {"Color.RED": "#ff0000"}, {"RED": "38;5;196"}),
        ("test3", {"Token.Color.RED": "#ff0000"}, {"RED": "38;5;196"}),
        ("test4", {"BOLD_RED": "bold #ff0000"}, {"BOLD_RED": "1;38;5;196"}),
        (
            "test5",
            {"INTENSE_RED": "italic underline bg:#ff0000 #ff0000"},
            {"INTENSE_RED": "3;4;48;5;196;38;5;196"},
        ),
        (
            "test6",
            {"INTENSE_GREEN": "reverse blink hidden bg:#ff0000 #ff0000"},
            {"INTENSE_GREEN": "7;5;8;48;5;196;38;5;196"},
        ),
        (
            "test6",
            {"INTENSE_BLUE": "noreverse noblink nohidden bg:#ff0000 #ff0000"},
            {"INTENSE_BLUE": "27;25;28;48;5;196;38;5;196"},
        ),
    ],
)
def test_register_custom_ansi_style(name, styles, refrules):
    register_custom_ansi_style(name, styles)
    style = ansi_style_by_name(name)
    assert style is not None
    for key, value in refrules.items():
        assert style[key] == value
