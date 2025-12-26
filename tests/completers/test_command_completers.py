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


def test_complete_command(completion_context_parse):
    if ON_WINDOWS:
        command = "dir.exe"
    else:
        command = "grep"

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


def test_complete_command_with_alias_description(completion_context_parse, xession):
    """Test that alias descriptions are included in completions"""
    # Create test aliases with and without descriptions
    def test_alias_with_desc():
        """Test alias description"""
        return "echo test"
    
    def test_alias_no_desc():
        return "echo no desc"
    
    xession.aliases["testalias"] = test_alias_with_desc
    xession.aliases["nodescalias"] = test_alias_no_desc
    
    # Enable description display
    xession.env["CMD_COMPLETIONS_SHOW_DESC"] = True
    
    # Force cache update
    xession.commands_cache.update_cache()
    
    # Get completions for alias with description
    comps_with_desc = list(complete_command(
        completion_context_parse("testalia", 8).command
    ))
    
    # Find the completion for our alias
    alias_comp = None
    for comp in comps_with_desc:
        if str(comp) == "testalias":
            alias_comp = comp
            break
    
    assert alias_comp is not None, "testalias should be in completions"
    assert hasattr(alias_comp, 'description'), "Completion should have description"
    assert alias_comp.description == "Test alias description", f"Expected 'Test alias description', got '{alias_comp.description}'"
    
    # Get completions for alias without description
    comps_no_desc = list(complete_command(
        completion_context_parse("nodescalia", 10).command
    ))
    
    # Find the completion for alias without description
    alias_comp_no_desc = None
    for comp in comps_no_desc:
        if str(comp) == "nodescalias":
            alias_comp_no_desc = comp
            break
    
    assert alias_comp_no_desc is not None, "nodescalias should be in completions"
    assert hasattr(alias_comp_no_desc, 'description'), "Completion should have description"
    assert alias_comp_no_desc.description == "Alias", f"Expected 'Alias', got '{alias_comp_no_desc.description}'"
