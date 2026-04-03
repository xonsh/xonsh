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
    assert set(comps) == {"$WOWZER", "$WOWZER?"}


def test_rich_completions(xession, monkeypatch, parser):
    xession.env.update({"WOWZER": 1})
    xession.env.register("WOWZER", type=int, doc="Nice Docs!")

    context = parser.parse("$WOW", 4)
    completion = next(complete_environment_vars(context)[0])
    assert completion.display == "$WOWZER [int]"
    assert completion.description == "Nice Docs!"


def test_question_mark_completions(xession, monkeypatch, parser):
    """$VAR? completions should include type and default in description."""
    xession.env.update({"WOWZER": 1})
    xession.env.register("WOWZER", type=int, doc="Nice Docs!")

    context = parser.parse("$WOW", 4)
    comps = list(complete_environment_vars(context)[0])
    help_comp = next(c for c in comps if str(c) == "$WOWZER?")
    assert help_comp.display == "$WOWZER? [int]"
    assert "Nice Docs!" in help_comp.description
    assert "int" in help_comp.description


def test_question_mark_prefix(xession, monkeypatch, parser):
    """Typing $VAR? as prefix should complete to $VAR (and $VAR?)."""
    xession.env.update({"WOWZER": 1})
    xession.env.register("WOWZER", type=int, doc="Nice Docs!")

    context = parser.parse("$WOWZER?", 8)
    result = complete_environment_vars(context)
    assert result is not None
    comps, lprefix = result
    comp_set = set(comps)
    assert "$WOWZER" in comp_set
