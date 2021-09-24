import pytest
import tempfile
from os import sep

from xonsh.completers.tools import RichCompletion
from xonsh.completers.dirs import complete_cd, complete_rmdir
from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    CommandArg,
)

from tests.tools import ON_WINDOWS

COMPLETERS = {
    "cd": complete_cd,
    "rmdir": complete_rmdir,
}

CUR_DIR = "." if ON_WINDOWS else "./"
PARENT_DIR = ".." if ON_WINDOWS else "../"


@pytest.fixture(autouse=True)
def setup(xession, xonsh_execer):
    with tempfile.TemporaryDirectory() as tmp:
        xession.env["XONSH_DATA_DIR"] = tmp
        xession.env["CDPATH"] = set()


@pytest.fixture(params=list(COMPLETERS))
def cmd(request):
    return request.param


def test_not_cmd(cmd):
    """Ensure the cd completer doesn't complete other commands"""
    assert not COMPLETERS[cmd](
        CompletionContext(
            CommandContext(
                args=(CommandArg(f"not-{cmd}"),),
                arg_index=1,
            )
        )
    )


def complete_cmd(cmd, prefix, opening_quote="", closing_quote=""):
    result = COMPLETERS[cmd](
        CompletionContext(
            CommandContext(
                args=(CommandArg(cmd),),
                arg_index=1,
                prefix=prefix,
                opening_quote=opening_quote,
                closing_quote=closing_quote,
                is_after_closing_quote=bool(closing_quote),
            )
        )
    )
    assert result and len(result) == 2
    completions, lprefix = result
    assert lprefix == len(opening_quote) + len(prefix) + len(
        closing_quote
    )  # should override the quotes
    return completions


def complete_cmd_dirs(*a, **kw):
    return [r.value for r in complete_cmd(*a, **kw)]


def test_non_dir(cmd):
    with tempfile.NamedTemporaryFile(dir=".", suffix="_dummySuffix") as tmp:
        with pytest.raises(StopIteration):  # tmp is a file
            complete_cmd(cmd, tmp.name[:-2])


@pytest.fixture(scope="module")
def dir_path():
    with tempfile.TemporaryDirectory(dir=".", suffix="_dummyDir") as tmp_path:
        yield tmp_path


def test_dirs_only(cmd, dir_path):
    completions = complete_cmd(cmd, dir_path[:-2])
    assert completions == {dir_path + sep}


def test_opening_quotes(cmd, dir_path):
    assert complete_cmd(cmd, dir_path, opening_quote="r'") == {f"r'{dir_path}{sep}'"}


def test_closing_quotes(cmd, dir_path):
    prefix = dir_path
    exp = f"'''{dir_path}{sep}'''"
    if ON_WINDOWS:
        prefix = prefix.replace("\\", "\\\\")
        # the path completer converts to a raw string if there's a backslash
        exp = "r" + exp

    completions = complete_cmd(cmd, prefix, opening_quote="'''", closing_quote="'''")

    assert completions == {exp}

    completion = completions.pop()
    assert isinstance(completion, RichCompletion)
    assert completion.append_closing_quote is False


def test_complete_dots(xession):
    with xession.env.swap(COMPLETE_DOTS="never"):
        dirs = complete_cmd_dirs("cd", "")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

        dirs = complete_cmd_dirs("cd", ".")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

    with xession.env.swap(COMPLETE_DOTS="matching"):
        dirs = complete_cmd_dirs("cd", "")
        assert CUR_DIR not in dirs and PARENT_DIR not in dirs

        dirs = complete_cmd_dirs("cd", ".")
        assert CUR_DIR in dirs and PARENT_DIR in dirs

    with xession.env.swap(COMPLETE_DOTS="always"):
        dirs = complete_cmd_dirs("cd", "")
        assert CUR_DIR in dirs and PARENT_DIR in dirs

        dirs = complete_cmd_dirs("cd", ".")
        assert CUR_DIR in dirs and PARENT_DIR in dirs
