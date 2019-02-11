"""Tests ANSI color tools."""
import pytest

from xonsh.ansi_colors import ansi_color_escape_code_to_name, ansi_reverse_style

RS = ansi_reverse_style(style='default')


@pytest.mark.parametrize('key, value', [
    ('', 'NO_COLOR'),
    ('31', 'RED'),
])
def test_ansi_reverse_style(key, value):
    assert key in RS
    assert RS[key] == value


@pytest.mark.parametrize('inp, exp', [
    ('0', ('NO_COLOR',)),
    ('\0010\002', ('NO_COLOR',)),
    ('\033[0m', ('NO_COLOR',)),
    ('\001\033[0m\002', ('NO_COLOR',)),
    ('00;36', ('CYAN',)),
    ('01;31', ('BOLD_RED',)),
    ('04;31', ('UNDERLINE_RED',)),
    ('1;4;31', ('BOLD_UNDERLINE_RED',)),
    ('4;1;31', ('BOLD_UNDERLINE_RED',)),
    ('31;42', ('RED', 'BACKGROUND_GREEN')),
    ('42;31', ('BACKGROUND_GREEN', 'RED')),
    ('40', ('BACKGROUND_BLACK',)),
    ('38;5;89', ('PURPLE',),),
    ('48;5;89', ('BACKGROUND_PURPLE',),),
    ('38;2;170;0;0', ('RED',),),
    ('48;2;170;0;0', ('BACKGROUND_RED',),),
])
def test_ansi_color_escape_code_to_name(inp, exp):
    obs = ansi_color_escape_code_to_name(inp, reversed_style=RS)
    assert obs == exp