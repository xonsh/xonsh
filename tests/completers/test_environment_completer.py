import pytest

from xonsh.environ import Env
from xonsh.parsers.completion_context import CompletionContextParser
from xonsh.completers.environment import complete_environment_vars


@pytest.fixture(scope="session")
def parser():
    return CompletionContextParser()


@pytest.mark.parametrize(
    "cmd",
    (
        "ls $WO",
        "ls /home/$WO",
        "ls @('hi ' + $WO",
    ),
)
def test_simple(cmd, xession, monkeypatch, parser):
    monkeypatch.setattr(xession, "env", Env({"WOW": 1}))

    context = parser.parse(cmd, len(cmd))
    comps, lprefix = complete_environment_vars(context)
    assert lprefix == 3
    assert set(comps) == {"$WOW"}


def test_rich_completions(xession, monkeypatch, parser):
    monkeypatch.setattr(xession, "env", Env({"WOW": 1}))
    xession.env.register("WOW", type=int, doc="Nice Docs!")

    context = parser.parse("$WO", 3)
    completion = next(complete_environment_vars(context)[0])
    assert completion.display == "$WOW [int]"
    assert completion.description == "Nice Docs!"
