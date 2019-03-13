"""Tests pygments hooks."""
import pytest

from xonsh.pyghooks import Color, color_name_to_pygments_code, code_by_name


DEFAULT_STYLES = {
    # Reset
    Color.NO_COLOR: "noinherit",  # Text Reset
    # Regular Colors
    Color.BLACK: "ansiblack",
    Color.BLUE: "ansiblue",
    Color.CYAN: "ansicyan",
    Color.GREEN: "ansigreen",
    Color.PURPLE: "ansimagenta",
    Color.RED: "ansired",
    Color.WHITE: "ansigray",
    Color.YELLOW: "ansiyellow",
    Color.INTENSE_BLACK: "ansibrightblack",
    Color.INTENSE_BLUE: "ansibrightblue",
    Color.INTENSE_CYAN: "ansibrightcyan",
    Color.INTENSE_GREEN: "ansibrightgreen",
    Color.INTENSE_PURPLE: "ansibrightmagenta",
    Color.INTENSE_RED: "ansibrightred",
    Color.INTENSE_WHITE: "ansiwhite",
    Color.INTENSE_YELLOW: "ansibrightyellow",
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
def test_code_by_name(name, exp):
    styles = DEFAULT_STYLES.copy()
    obs = code_by_name(name, styles)
    assert obs == exp
