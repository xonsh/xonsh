import pytest

from tests.tools import ON_WINDOWS
from xonsh.completers.pip import PIP_RE


@pytest.mark.parametrize(
    "line",
    [
        "pip",
        "pip.exe",
        "pip3.6.exe",
        "xpip",
        "/usr/bin/pip3",
        r"C:\Python\Scripts\pip",
        r"C:\Python\Scripts\pip.exe",
    ],
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


@pytest.mark.parametrize(
    "line, prefix, exp",
    [
        ["pip", "c", {"cache", "check", "config"}],
        ["pip show", "", {"setuptools", "wheel", "pip"}],
    ],
)
def test_completions(
    line, prefix, exp, check_completer, xession, monkeypatch, session_vars
):
    if ON_WINDOWS:
        line = line.replace("pip", "pip.exe")
    # needs original env for subproc all on all platforms
    monkeypatch.setattr(xession, "env", session_vars["env"])
    comps = check_completer(line, prefix=prefix)

    assert comps.intersection(exp)
