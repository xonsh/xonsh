import os

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


@pytest.mark.parametrize(
    "line, prefix, exp",
    [
        ["pip", "c", {"cache", "check", "config"}],
        ["pip show", "", {"setuptools", "wheel", "pip"}],
    ],
)
def test_completions(line, prefix, exp, check_completer, xession, tmp_path):
    xession.env["XONSH_DATA_DIR"] = tmp_path
    xession.env["PATH"] = os.environ["PATH"]
    comps = check_completer(line, prefix=prefix)

    assert comps.intersection(exp)
