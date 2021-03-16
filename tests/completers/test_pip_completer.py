import pytest

from xonsh.completers.tools import RichCompletion
from xonsh.completers.pip import PIP_RE, complete_pip
from xonsh.parsers.completion_context import CompletionContext, CommandContext, CommandArg


@pytest.mark.parametrize(
    "line", ["pip", "xpip", "/usr/bin/pip3", r"C:\Python\Scripts\pip"]
)
def test_pip_re(line):
    assert PIP_RE.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "bagpipes show",
        "toxbagpip uninstall",
        "$(tompippery show",
        "![thewholepipandpaboodle uninstall",
        "$[littlebopip show",
        "!(boxpip uninstall",
        "pipx",
        "vim pip_",
        "pip_",
    ],
)
def test_pip_list_re1(line):
    assert PIP_RE.search(line) is None


def test_commands():
    comps = complete_pip(CompletionContext(CommandContext(
        args=(CommandArg("pip3"),), arg_index=1,
        prefix="c",
    )))
    assert comps.intersection({"cache", "check", "config"})
    for comp in comps:
        assert isinstance(comp, RichCompletion)
        assert comp.append_space


def test_package_list():
    comps = complete_pip(CompletionContext(CommandContext(
        args=(CommandArg("pip3"), CommandArg("show")), arg_index=2,
    )))
    assert "Package" not in comps
    assert "-----------------------------" not in comps
    assert "pytest" in comps
