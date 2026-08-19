import pytest

from xonsh.lib.string import endswith_newline, unquote


@pytest.mark.parametrize(
    "value, expected",
    [
        ('"quoted"', "quoted"),
        ("'quoted'", "quoted"),
        ("\"mismatched'", "\"mismatched'"),
        ("plain", "plain"),
    ],
)
def test_unquote(value: str, expected: str):
    assert unquote(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("text", "text\n"), ("text\n", "text\n"), ("text\n\n", "text\n"), ("", "\n")],
)
def test_endswith_newline(value: str, expected: str):
    assert endswith_newline(value) == expected
