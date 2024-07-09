import builtins
import os.path
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from xonsh.aliases import make_default_aliases, source_alias


@pytest.fixture
def mockopen(xession, monkeypatch):
    @contextmanager
    def mocked_open(fpath, *args, **kwargs):
        yield MagicMock(read=lambda: fpath)

    monkeypatch.setattr(builtins, "open", mocked_open)


@pytest.fixture
def mocked_execx_checker(xession, monkeypatch):
    checker = []

    def mocked_execx(src, *args, **kwargs):
        checker.append(src.strip())

    monkeypatch.setattr(xession.builtins, "execx", mocked_execx)
    return checker


def test_source_current_dir(mockopen, monkeypatch, mocked_execx_checker):
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    source_alias(["foo", "bar"])
    assert mocked_execx_checker == ["foo", "bar"]


def test_source_path(mockopen, mocked_execx_checker, xession):
    with xession.env.swap(PATH=[Path(__file__).parent.parent / "bin"]):
        source_alias(["foo", "bar"])
    path_foo = os.path.join("bin", "foo")
    path_bar = os.path.join("bin", "bar")
    assert mocked_execx_checker[0].endswith(path_foo)
    assert mocked_execx_checker[1].endswith(path_bar)


@pytest.mark.parametrize(
    "alias",
    [
        "source-bash",
        "source-zsh",
    ],
)
def test_source_foreign_fn_parser(alias, xession):
    aliases = make_default_aliases()
    source_bash = aliases[alias]

    positionals = [act.dest for act in source_bash.parser._get_positional_actions()]
    options = [act.dest for act in source_bash.parser._get_optional_actions()]

    assert positionals == ["files_or_code"]
    assert options == [
        "help",
        "interactive",
        "login",
        "envcmd",
        "aliascmd",
        "extra_args",
        "safe",
        "prevcmd",
        "postcmd",
        "funcscmd",
        "sourcer",
        "use_tmpfile",
        "seterrprevcmd",
        "seterrpostcmd",
        "overwrite_aliases",
        "suppress_skip_message",
        "show",
        "dryrun",
        "interactive",
    ]
