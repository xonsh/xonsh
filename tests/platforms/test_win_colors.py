from xonsh import tools
from xonsh.platforms import win_colors


def test_win10_color_map():
    assert win_colors.WIN10_COLOR_MAP["ansired"] == "#c50f1f"
    assert win_colors.WIN10_COLOR_MAP["ansibrightcyan"] == "#61d6d6"


def test_hardcode_colors_for_win10(xession):
    xession.env["PROMPT_TOOLKIT_COLOR_DEPTH"] = ""
    style_map = {
        "plain": "ansired",
        "bold": "bold ansiblue",
        "nobold": "nobold ansigreen",
    }

    result = win_colors.hardcode_colors_for_win10(style_map)

    assert result == {
        "plain": "#c50f1f",
        "bold": " #3b78ff",
        "nobold": "nobold #13a10e",
    }
    assert xession.env["PROMPT_TOOLKIT_COLOR_DEPTH"] == "DEPTH_24_BIT"


def test_tools_reexports_windows_color_helpers():
    assert tools.WIN10_COLOR_MAP == win_colors.WIN10_COLOR_MAP
    assert tools.WIN_BOLD_COLOR_MAP == win_colors.WIN_BOLD_COLOR_MAP
    assert tools.hardcode_colors_for_win10 is win_colors.hardcode_colors_for_win10
