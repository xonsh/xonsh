import pytest

from xonsh.completers.pip import PIP_RE


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


def test_commands(check_completer):
    comps = check_completer("pip", prefix="c")

    assert comps.intersection({"cache", "check", "config"})


def test_package_list(check_completer):
    comps = check_completer("pip show")
    assert "Package" not in comps
    assert "-----------------------------" not in comps
    assert "setuptools" in comps
