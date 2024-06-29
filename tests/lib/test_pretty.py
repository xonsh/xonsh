import re

import pytest

from xonsh.lib import pretty

long_list = ["str"] * 30
long_list_exp = "[" + (",\n ".join(["'str'"] * 30) + "]")
nested_long_list_exp = "[[" + (",\n  ".join(["'str'"] * 30) + "]]")
cases = [
    (1, "1"),
    (1.0, "1.0"),
    pytest.param(long_list, long_list_exp, id="long-list"),
    pytest.param([long_list], nested_long_list_exp, id="nested-long-list"),
    pytest.param(re.compile, "<function re.compile>", id="function"),
    (Exception, "Exception"),
    ({}, "{}"),
    pytest.param(
        dict(zip(range(30), range(100, 130))),
        """\
{0: 100,
 1: 101,
 2: 102,
 3: 103,
 4: 104,
 5: 105,
 6: 106,
 7: 107,
 8: 108,
 9: 109,
 10: 110,
 11: 111,
 12: 112,
 13: 113,
 14: 114,
 15: 115,
 16: 116,
 17: 117,
 18: 118,
 19: 119,
 20: 120,
 21: 121,
 22: 122,
 23: 123,
 24: 124,
 25: 125,
 26: 126,
 27: 127,
 28: 128,
 29: 129}""",
        id="long-dict",
    ),
    (re.compile("1"), "re.compile(r'1', re.UNICODE)"),
    pytest.param(
        dict([(0, 0), (2, 1), (1, 2), (4, 3), (3, 4)]),
        "{0: 0, 2: 1, 1: 2, 4: 3, 3: 4}",
        id="dict-preserve-order",
    ),
]


@pytest.mark.parametrize("obj, exp", cases)
def test_pretty_fn(obj, exp):
    result = pretty.pretty(obj)
    assert result == exp


def test_pretty_printer(capsys):
    pretty.pretty_print({})
    captured = capsys.readouterr()
    assert captured.out == "{}\n"
