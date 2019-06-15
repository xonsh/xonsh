"""Tests color tools."""
import pytest

from xonsh.color_tools import iscolor


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("NO_COLOR", True),
        ("CYAN", True),
        ("PURPLE", True),
        ("INTENSE_YELLOW", True),
        ("#fff", True),
        ("#FFF", True),
        ("#fafad2", True),
        ("#FAFAD2", True),
        ("BOLD_RED", True),
        ("BOLD_GREEN", True),
        ("UNDERLINE_RED", True),
        ("BOLD_UNDERLINE_RED", True),
        ("UNDERLINE_BOLD_RED", True),
        ("BACKGROUND_RED", True),
        ("BACKGROUND_GREEN", True),
        ("BACKGROUND_BLACK", True),
        ("BACKGROUND_PURPLE", True),
        ("BACKGROUND_INTENSE_RED", True),
        ("BACKGROUND_#123456", True),
        ("bg#fff", True),
        ("bg#fafad2", True),
        ("BG#fff", True),
        ("BG#fafad2", True),
        ("WAKKA", False),
        ("#F", False),
        ("#FAFAD", False),
        ("UNDERLINE_BACKGROUND_RED", False),
        ("BACKGROUND_BOLD_RED", False),
    ],
)
def test_iscolor(inp, exp):
    obs = iscolor(inp)
    if exp:
        assert obs
    else:
        assert not obs
