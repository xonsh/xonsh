import tempfile
from os import sep

import pytest

from xonsh.completers.tools import RichCompletion
from xonsh.pytest.tools import ON_WINDOWS

CUR_DIR = "." if ON_WINDOWS else "./"
PARENT_DIR = ".." if ON_WINDOWS else "../"


@pytest.fixture(autouse=True)
def setup(xession, xonsh_execer):
    with tempfile.TemporaryDirectory() as tmp:
        xession.env["XONSH_DATA_DIR"] = tmp
        xession.env["CDPATH"] = set()


@pytest.fixture(params=["cd", "rmdir"])
def cmd(request):
    return request.param


def test_non_dir(cmd, check_completer):
    with tempfile.NamedTemporaryFile(dir=".", suffix="_dummySuffix") as tmp:
        assert not check_completer(cmd, prefix=tmp.name[:-2])


@pytest.fixture(scope="module")
def dir_path():
    with tempfile.TemporaryDirectory(dir=".", suffix="_dummyDir") as tmp_path:
        yield tmp_path


def test_dirs_only(cmd, dir_path, check_completer):
    completions = check_completer(cmd, dir_path[:-2])
    assert completions == {dir_path + sep}


def test_opening_quotes(cmd, dir_path, check_completer):
    assert check_completer(cmd, "r'" + dir_path) == {f"r'{dir_path}{sep}'"}


def test_closing_quotes(cmd, dir_path, check_completer):
    prefix = dir_path
    exp = f"'''{dir_path}{sep}'''"
    if ON_WINDOWS:
        prefix = prefix.replace("\\", "\\\\")
        # the path completer converts to a raw string if there's a backslash
        exp = "r" + exp

    values, completions = check_completer(
        cmd, "'''" + prefix + "'''", send_original=True
    )

    assert values == {exp}

    completion = list(completions).pop()
    assert isinstance(completion, RichCompletion)
    assert completion.append_closing_quote is False


def test_complete_dots(xession, check_completer):
    with xession.env.swap(COMPLETE_DOTS="never"):
        dirs = check_completer("cd")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

        dirs = check_completer("cd", ".")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

    with xession.env.swap(COMPLETE_DOTS="matching"):
        dirs = check_completer("cd", "")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

        dirs = check_completer("cd", ".")
        assert CUR_DIR in dirs and PARENT_DIR in dirs

    with xession.env.swap(COMPLETE_DOTS="always"):
        dirs = check_completer("cd", "")
        assert CUR_DIR in dirs and PARENT_DIR in dirs

        dirs = check_completer("cd", ".")
        assert CUR_DIR in dirs and PARENT_DIR in dirs
