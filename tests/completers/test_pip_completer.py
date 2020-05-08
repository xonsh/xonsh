import pytest
from xonsh.completers.pip import PIP_RE, PIP_LIST_RE


@pytest.mark.parametrize(
    "line", ["pip", "xpip search", "$(pip", "![pip", "$[pip", "!(xpip"]
)
def test_pip_re(line):
    assert PIP_RE.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "pip show",
        "xpip uninstall",
        "$(pip show",
        "![pip uninstall",
        "$[pip show",
        "!(xpip uninstall",
    ],
)
def test_pip_list_re(line):
    assert PIP_LIST_RE.search(line)


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
