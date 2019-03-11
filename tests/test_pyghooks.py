"""Tests pygments hooks."""
import pytest

from xonsh.pyghooks import (
    color_name_to_pygments_code,
)


DEFAULT_STYLES = {
    # Reset
    "NO_COLOR": "noinherit",  # Text Reset
    # Regular Colors
    "BLACK": "ansiblack",
    "BLUE": "ansiblue",
    "CYAN": "ansicyan",
    "GREEN": "ansigreen",
    "PURPLE": "ansimagenta",
    "RED": "ansired",
    "WHITE": "ansigray",
    "YELLOW": "ansiyellow",
    "INTENSE_BLACK": "ansibrightblack",
    "INTENSE_BLUE": "ansibrightblue",
    "INTENSE_CYAN": "ansibrightcyan",
    "INTENSE_GREEN": "ansibrightgreen",
    "INTENSE_PURPLE": "ansibrightmagenta",
    "INTENSE_RED": "ansibrightred",
    "INTENSE_WHITE": "ansiwhite",
    "INTENSE_YELLOW": "ansibrightyellow",
}


@pytest.mark.parametrize(
    "name, exp",
    [
        ("NO_COLOR", "noinherit"),
        ("RED", "ansired"),
        ("BACKGROUND_RED", "bg:ansired"),
        ("BACKGROUND_INTENSE_RED", "bg:ansibrightred"),
        ("BOLD_RED", "bold ansired"),
        ("UNDERLINE_RED", "underline ansired"),
        ("BOLD_UNDERLINE_RED", "bold underline ansired"),
        ("UNDERLINE_BOLD_RED", "underline bold ansired"),
        # test unsupported modifiers
        ("BOLD_FAINT_RED", "bold ansired"),
        ("BOLD_SLOWBLINK_RED", "bold ansired"),
        ("BOLD_FASTBLINK_RED", "bold ansired"),
        ("BOLD_INVERT_RED", "bold ansired"),
        ("BOLD_CONCEAL_RED", "bold ansired"),
        ("BOLD_STRIKETHROUGH_RED", "bold ansired"),
        # test hexes
        ("#000", "#000"),
        ("#000000", "#000000"),
        ("BACKGROUND_#000", "bg:#000"),
        ("BACKGROUND_#000000", "bg:#000000"),
        ("BG#000", "bg:#000"),
        ("bg#000000", "bg:#000000"),
    ],
)
def test_color_name_to_pygments_code(name, exp):
    styles = DEFAULT_STYLES.copy()
    obs = color_name_to_pygments_code(name, styles)
    assert obs == exp
