import pytest

from tests.tools import ON_WINDOWS
from xonsh.completers.commands import complete_xompletions


regex_cases = [
    "pip",
    "pip.exe",
    "pip3.6.exe",
    "xpip",
]

if ON_WINDOWS:
    regex_cases.append(r"C:\Python\Scripts\pip")
    regex_cases.append(r"C:\Python\Scripts\pip.exe")
else:
    regex_cases.append("/usr/bin/pip3")


@pytest.mark.parametrize(
    "line",
    regex_cases,
)
def test_pip_re(line):
    assert complete_xompletions.search_completer(line)


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
    assert complete_xompletions.search_completer(line) is None


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
