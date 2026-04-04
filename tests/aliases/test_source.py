import builtins
import os.path
import shlex
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from xonsh.aliases import make_default_aliases, source_alias_fn, source_foreign_fn
from xonsh.tools import argvquote


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


def _spy_foreign_shell(monkeypatch):
    calls = {}

    def fake_foreign_shell_data(*args, **kwargs):
        calls["kwargs"] = kwargs
        return {}, {}

    fake_foreign_shell_data.cache_clear = lambda: None
    monkeypatch.setattr(
        "xonsh.aliases.foreign_shell_data", fake_foreign_shell_data, raising=False
    )
    return calls


def test_source_foreign_quotes_posix_paths(monkeypatch, xession):
    calls = _spy_foreign_shell(monkeypatch)
    monkeypatch.setattr(os.path, "isfile", lambda _: True)
    target = "/Applications/Visual Studio Code.app/foo.sh"

    source_foreign_fn("bash", [target], sourcer="source")

    expected = f"source {shlex.quote(target)}\n"
    assert calls["kwargs"]["prevcmd"] == expected


def test_source_foreign_quotes_cmd_paths(monkeypatch, xession):
    calls = _spy_foreign_shell(monkeypatch)
    monkeypatch.setattr(os.path, "isfile", lambda _: True)
    target = r"C:\\Program Files\\foo.bat"

    source_foreign_fn("cmd.exe", [target], sourcer="call")

    expected = f"call {argvquote(target, force=True)}\n"
    assert calls["kwargs"]["prevcmd"] == expected
