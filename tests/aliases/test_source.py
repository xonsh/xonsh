import builtins
import os.path
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from xonsh.aliases import make_default_aliases, source_alias_fn


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


def test_source_files(mockopen, monkeypatch, mocked_execx_checker):
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    files = [".xonshrc", "foo.xsh", "bar.xonshrc", "py.py"]
    source_alias_fn(files)
    assert mocked_execx_checker == files


def test_source_files_any_ext_exception(mockopen, monkeypatch, mocked_execx_checker):
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    with pytest.raises(RuntimeError):
        source_alias_fn(["foo.bar", "bar.foo", ".foobar"])


def test_source_files_any_ext(mockopen, monkeypatch, mocked_execx_checker):
    monkeypatch.setattr(os.path, "isfile", lambda x: True)
    files = [
        "foo.bar",
        "bar.foo",
        ".foobar",
        ".xonshrc",
        "foo.xsh",
        "bar.xonshrc",
        "py.py",
    ]
    source_alias_fn(files, ignore_ext=True)
    assert mocked_execx_checker == files


def test_source_from_env_path(mockopen, mocked_execx_checker, xession):
    with xession.env.swap(PATH=[Path(__file__).parent.parent / "bin"]):
        source_alias_fn(["foo", "bar"], ignore_ext=True)
    assert mocked_execx_checker[0].endswith("foo")
    assert mocked_execx_checker[1].endswith("bar")


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
