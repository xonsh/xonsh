from unittest.mock import Mock

import pytest

from xonsh.completer import Completer
from xonsh.completers.commands import complete_command, complete_skipper
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)
from xonsh.pytest.tools import ON_WINDOWS, completions_from_result, skip_if_on_windows


@pytest.fixture(autouse=True)
def xs_orig_commands_cache(xession):
    pass


def test_complete_command(completion_context_parse, tmp_path, xession):
    command = "somefile.exe" if ON_WINDOWS else "somefile"
    tmpdir = tmp_path / "test_complete_command"
    tmpdir.mkdir()
    testfile = tmpdir / command
    testfile.write_text("some file")
    testfile.chmod(0o777)

    xession.env["PATH"].append(str(tmpdir))
    comps = complete_command(
        completion_context_parse(command[:-1], len(command) - 1).command
    )
    assert command in set(map(str, comps))


@skip_if_on_windows
def test_skipper_command(completion_context_parse):
    assert "grep" in completions_from_result(
        complete_skipper(completion_context_parse("sudo gre", 8))
    )


@skip_if_on_windows
def test_skipper_arg(completion_context_parse, xession, monkeypatch):
    monkeypatch.setattr(xession.shell.shell, "completer", Completer(), raising=False)
    bash_completer_mock = Mock()
    monkeypatch.setattr(xession, "_completers", {"bash": bash_completer_mock})

    bash_completer_mock.return_value = {"--count "}

    assert "--count " in completions_from_result(
        complete_skipper(completion_context_parse("sudo grep --coun", 16))
    )

    call_args = bash_completer_mock.call_args[0]
    assert len(call_args) == 1

    context = call_args[0]
    assert isinstance(context, CompletionContext)
    assert context.command == CommandContext(
        args=(CommandArg("grep"),), arg_index=1, prefix="--coun"
    )


def test_argparse_completer(check_completer, monkeypatch):
    assert check_completer("xonsh", prefix="-").issuperset(
        {
            "--cache-everything",
            "--help",
            "--interactive",
            "--login",
            "--no-env",
            "--no-rc",
            "--no-script-cache",
            "--rc",
            "--shell-type",
            "--timings",
            "--version",
        }
    )


def test_argparse_completer_after_option(check_completer, tmp_path):
    prefix = str(tmp_path)[:-1]
    # has one or more completions including the above tmp_path
    assert check_completer("xonsh --no-rc", prefix)


def test_argparse_completer_unknown_option(check_completer):
    """Completer must not crash on an unknown option that looks like a flag.

    Regression: ``xontrib load -p <TAB>`` raised
    ``AttributeError: 'NoneType' object has no attribute 'nargs'`` because
    ``argparse._parse_optional`` returns ``(None, arg, None, None)`` when the
    token starts with a prefix char but matches no known option.
    """
    # Should not raise. Result may be empty — we only assert no crash.
    check_completer("xontrib load -p", prefix="")


@skip_if_on_windows
def test_complete_command_substring(completion_context_parse):
    """Completers should match by substring, not just prefix (xonsh#6082)."""
    # 'grep' should match prefix 'rep' via substring
    comps = set(map(str, complete_command(completion_context_parse("rep", 3).command)))
    assert "grep" in comps


def test_filter_function_substring(xession):
    """Filter functions should use case-insensitive substring matching."""
    from xonsh.completers.tools import (
        RichCompletion,
        _filter_substring,
    )

    # case-insensitive substring match (middle of string)
    assert _filter_substring("Dev-Xonsh-Deploy", "deploy")
    assert _filter_substring("ASDFGH", "asd")
    assert not _filter_substring("asdfgh", "xyz")

    # prefix match should still work
    assert _filter_substring("asdfgh", "asdf")

    # empty prefix matches everything
    assert _filter_substring("anything", "")
    # prefix longer than text
    assert not _filter_substring("ls", "longprefix")

    # RichCompletion with display text
    assert _filter_substring(RichCompletion("val", display="Foo, Bar-Deploy"), "deploy")
    assert not _filter_substring(RichCompletion("val", display="foo, bar"), "xyz")
