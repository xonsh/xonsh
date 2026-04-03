from unittest.mock import MagicMock

import pytest

import xonsh.shells.readline_shell as rlshell
from xonsh.completers.tools import RichCompletion
from xonsh.shells.readline_shell import _align_completion


def test_align_completion_pure():
    assert _align_completion("json", 3, 3, 0, "jso") == "json"
    assert _align_completion("a.bc", 3, 1, 2, "a.b") == "bc"
    assert _align_completion("bc", 1, 3, 0, "a.b") == "a.bc"

    # NOTE: "bbc" may be semantically unexpected in real usage.
    # This test documents current formula behavior for the begidx > 0 edge case,
    # flagged for follow-up review.
    assert _align_completion("bc", 0, 1, 2, "a.b") == "bbc"
    assert _align_completion("x.yz", 3, 1, 2, "a.b") is None


def test_completedefault_integration_safe_path(readline_shell, monkeypatch):
    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=1))

    mock_completer = MagicMock()
    mock_completer.complete.return_value = (("det_enc", "det_dec"), 3)
    readline_shell.completer = mock_completer

    res = readline_shell.completedefault("det", "det", 0, 3)

    # Assert EXACT returned list to verify _complete_only_last_table didn't silently transform values
    assert res == ["det_enc", "det_dec"]


def test_completedefault_integration_rich_metadata(readline_shell, monkeypatch):
    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=1))

    mock_completer = MagicMock()
    comp = RichCompletion("json", prefix_len=3, append_space=True)
    mock_completer.complete.return_value = ((comp,), 3)
    readline_shell.completer = mock_completer

    res = readline_shell.completedefault("jso", "jso", 0, 3)

    assert len(res) == 1
    assert isinstance(res[0], RichCompletion)
    assert res[0] == "json"
    assert getattr(res[0], "append_space", False) is True


def test_completedefault_show_path_2(readline_shell, monkeypatch):
    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    # show_completions == 2: no common prefix, under query limit
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=2))

    mock_completer = MagicMock()
    mock_completer.complete.return_value = (("det_enc", "det_dec"), 3)
    readline_shell.completer = mock_completer

    res = readline_shell.completedefault("det", "det", 0, 3)

    # show_completions==2 must return the aligned rtn list, not raw orig_completions
    assert res == ["det_enc", "det_dec"]


@pytest.mark.parametrize(
    "line, exp",
    [
        [repr("hello"), "hello"],
        ["2 * 3", "6"],
    ],
)
def test_rl_prompt_cmdloop(line, exp, readline_shell, capsys):
    shell = readline_shell
    shell.use_rawinput = False
    shell.stdin.write(f"{line}\nexit\n")  # note: terminate with '\n'
    shell.stdin.seek(0)
    shell.cmdloop()
    # xonsh, doesn't write all its output to shell.stdout
    # so capture sys.stdout
    out, err = capsys.readouterr()

    # sometimes the output has ansii color codes
    assert exp in out.strip()
