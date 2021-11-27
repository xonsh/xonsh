import pytest

from xonsh.completers._aliases import add_one_completer
from xonsh.completers.tools import non_exclusive_completer

SIMPLE = lambda: None
NON_EXCLUSIVE = non_exclusive_completer(lambda: None)


@pytest.mark.parametrize(
    "initial, exp",
    (
        ({}, ["new"]),
        ({"simp": SIMPLE}, ["new", "simp"]),
        ({"nx": NON_EXCLUSIVE}, ["nx", "new"]),
        ({"nx": NON_EXCLUSIVE, "simp": SIMPLE}, ["nx", "new", "simp"]),
        (
            {"ctx1": NON_EXCLUSIVE, "ctx2": NON_EXCLUSIVE, "simp": SIMPLE},
            ["ctx1", "ctx2", "new", "simp"],
        ),
        (
            {"ctx1": NON_EXCLUSIVE, "ctx2": NON_EXCLUSIVE, "simp": SIMPLE},
            ["ctx1", "ctx2", "new", "simp"],
        ),
        (
            {"ctx1": NON_EXCLUSIVE, "simp": SIMPLE, "ctx2": NON_EXCLUSIVE},
            ["ctx1", "new", "simp", "ctx2"],
        ),
    ),
)
def test_add_completer_start(monkeypatch, initial, exp, xession):
    xession.completers.clear()
    xession.completers.update(initial)
    add_one_completer("new", SIMPLE, "start")
    assert list(xession.completers.keys()) == exp
