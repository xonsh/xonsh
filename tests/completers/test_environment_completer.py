import pytest

from xonsh.parsers.completion_context import CompletionContextParser
from xonsh.completers.environment import complete_environment_vars


@pytest.fixture(scope="session")
def parser():
    return CompletionContextParser()


@pytest.mark.parametrize("cmd", (
    "ls $WO",
    "ls /home/$WO",
    "ls @('hi ' + $WO",
))
def test_simple(cmd, xonsh_builtins, monkeypatch, parser):
    monkeypatch.setitem(xonsh_builtins.__xonsh__.env, "WOW", 1)

    context = parser.parse(cmd, len(cmd))
    assert complete_environment_vars(context) == ({"$WOW"}, 3)
