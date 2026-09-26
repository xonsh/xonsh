from xonsh.lib.itertools import all_permutations, get_portions
from xonsh.tools import all_permutations as tools_all_permutations
from xonsh.tools import get_portions as tools_get_portions


def test_all_permutations_covers_every_non_empty_length():
    assert list(all_permutations("AB")) == [("A",), ("B",), ("A", "B"), ("B", "A")]


def test_get_portions_supports_negative_slices():
    assert list(get_portions(it=range(5), slices=slice(-2, None))) == [3, 4]


def test_tools_keeps_compatibility_exports():
    assert tools_all_permutations is all_permutations
    assert tools_get_portions is get_portions
