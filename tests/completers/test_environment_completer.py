import pytest

from xonsh.completers.environment import complete_environment_vars
from xonsh.parsers.completion_context import CompletionContextParser


@pytest.fixture(scope="session")
def parser():
    return CompletionContextParser()


@pytest.mark.parametrize(
    "cmd",
    (
        "ls $WOW",
        "ls /home/$WOW",
        "ls '/home/$WOW'",
        "ls @('hi ' + $WOW",
    ),
)
def test_simple(cmd, xession, monkeypatch, parser):
    xession.env.update({"WOWZER": 1})

    context = parser.parse(cmd, len(cmd))
    comps, lprefix = complete_environment_vars(context)
    # account for the ending quote
    if cmd[-1] in "'":
        assert lprefix == 5
    else:
        assert lprefix == 4
    assert set(comps) == {"$WOWZER"}


def test_rich_completions(xession, monkeypatch, parser):
    xession.env.update({"WOW": 1})
    xession.env.register("WOW", type=int, doc="Nice Docs!")

    context = parser.parse("$WO", 3)
    completion = next(complete_environment_vars(context)[0])
    assert completion.display == "$WOW [int]"
    assert completion.description == "Nice Docs!"
