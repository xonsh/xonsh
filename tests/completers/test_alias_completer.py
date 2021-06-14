import os
import stat

import pytest

from xonsh.completers.completer import complete_argparser_aliases
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)
from xonsh.platform import ON_WINDOWS


@pytest.fixture
def xsh_with_aliases(xession, monkeypatch):
    from xonsh.aliases import Aliases, make_default_aliases

    xsh = xession
    monkeypatch.setattr(xsh, "aliases", Aliases(make_default_aliases()))
    return xsh


def check_completer(args: str, exp: set, **kwargs):
    cmds = tuple(CommandArg(i) for i in args.split(" "))
    arg_index = len(cmds)
    completions = complete_argparser_aliases(
        CompletionContext(CommandContext(args=cmds, arg_index=arg_index, **kwargs))
    )
    comp_values = {getattr(i, "value", i) for i in completions}
    assert comp_values == exp


@pytest.mark.parametrize(
    "args, exp",
    [
        (
            "completer",
            {"add", "remove", "rm", "list", "ls", "--help", "-h"},
        ),
        (
            "completer add",
            {"--help", "-h"},
        ),
        (
            "completer add newcompleter",
            {"--help", "-h", "three", "four"},
        ),
        (
            "completer add newcompleter three",
            {"<one", "--help", ">two", ">one", "<two", "end", "-h", "start"},
        ),
        (
            "completer remove",
            {"--help", "-h", "one", "two"},
        ),
        (
            "completer list",
            {"--help", "-h"},
        ),
    ],
)
def test_completer_command(args, exp, xsh_with_aliases, monkeypatch):
    xsh = xsh_with_aliases
    monkeypatch.setattr(xsh, "completers", {"one": 1, "two": 2})
    monkeypatch.setattr(xsh, "ctx", {"three": lambda: 1, "four": lambda: 2})
    check_completer(args, exp)


@pytest.mark.parametrize(
    "args, prefix, exp",
    [
        (
            "xonfig",
            "-",
            {"-h", "--help"},
        ),
        (
            "xonfig colors",
            "b",
            {"blue", "brown"},
        ),
    ],
)
def test_xonfig(args, prefix, exp, xsh_with_aliases, monkeypatch):
    from xonsh import xonfig

    monkeypatch.setattr(xonfig, "color_style_names", lambda: ["blue", "brown", "other"])
    check_completer(args, exp, prefix=prefix)


def test_xontrib(xsh_with_aliases):
    check_completer("xontrib", {"list", "load"}, prefix="l")


@pytest.fixture
def venvs(tmpdir):
    """create bin paths in the tmpdir"""
    from xonsh.dirstack import _pushd, _popd

    _pushd(str(tmpdir))
    paths = []
    for idx in range(2):
        bin_path = tmpdir / f"venv{idx}" / "bin"
        paths.append(bin_path)

        (bin_path / "python").write("", ensure=True)
        (bin_path / "python.exe").write("", ensure=True)
        for file in bin_path.listdir():
            st = os.stat(str(file))
            os.chmod(str(file), st.st_mode | stat.S_IEXEC)
    yield paths
    _popd()


_VENV_NAMES = {"--help", "venv1", "-h", "venv1/", "venv0/", "venv0"}
if ON_WINDOWS:
    _VENV_NAMES = {"--help", "-h", "venv1\\", "venv0\\"}


@pytest.mark.parametrize(
    "args, exp",
    [
        (
            "vox",
            {
                "delete",
                "-h",
                "new",
                "remove",
                "del",
                "workon",
                "list",
                "exit",
                "ls",
                "help",
                "rm",
                "deactivate",
                "activate",
                "enter",
                "--help",
                "create",
            },
        ),
        (
            "vox create",
            {
                "--copies",
                "--symlinks",
                "--ssp",
                "--system-site-packages",
                "--activate",
                "--without-pip",
                "--interpreter",
                "-p",
                "-a",
                "--help",
                "-h",
            },
        ),
        ("vox activate", _VENV_NAMES),
        ("vox rm", _VENV_NAMES),
        ("vox rm venv1", _VENV_NAMES),  # nargs: one-or-more
        ("vox rm venv1 venv2", _VENV_NAMES),  # nargs: one-or-more
    ],
)
def test_vox_completer(args, exp, xsh_with_aliases, load_vox, venvs, monkeypatch):
    check_completer(args, exp)
