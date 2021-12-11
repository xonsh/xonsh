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
def test_completions(line, prefix, exp, check_completer, xession, os_env, monkeypatch):
    # use the actual PATH from os. Otherwise subproc will fail on windows. `unintialized python...`
    monkeypatch.setattr(xession, "env", os_env)

    if ON_WINDOWS:
        line = line.replace("pip", "pip.exe")
    comps = check_completer(line, prefix=prefix)

    assert comps.intersection(exp)
