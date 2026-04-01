import pytest
from unittest.mock import MagicMock

from xonsh.completers.tools import RichCompletion


def test_completedefault_prefix_safety(readline_shell, monkeypatch):
    """
    Test that completedefault filters out substring matches that do not
    start with the prompt's prefix, preventing the 'prefix swallowing' bug.
    """
    import xonsh.shells.readline_shell as rlshell
    
    # Mock readline interactions that completedefault calls
    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    
    # Mock the querycompletions display prompt (return 2 = return completions directly)
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=2))
    
    # Mock the completer return values
    mock_completer = MagicMock()
    # Return two completions: one exact prefix match, one substring match
    mock_completer.complete.return_value = (
        {
            RichCompletion("@.imp.json", prefix_len=9),
            RichCompletion("@.imp._json", prefix_len=9),
        },
        9 # plen
    )
    readline_shell.completer = mock_completer
    
    # Execute completedefault with user input "@.imp.jso"
    results = readline_shell.completedefault("@.imp.jso", "@.imp.jso", 0, 9)
    
    # Verify the substring match (_json) was filtered out to protect readline's common prefix
    result_strs = [str(r) for r in results]
    assert "@.imp.json" in result_strs
    assert "@.imp._json" not in result_strs


@pytest.mark.parametrize(
    "prefix, line, begidx, endidx, plen, mock_comp, expected_str, expected_type",
    [
        # Xonsh plen == Readline plen (No offset/pad, just match check)
        ("jso", "jso", 0, 3, 3, RichCompletion("json", prefix_len=3), "json", RichCompletion),
        
        # Xonsh plen > Readline plen (Trim offset from front of completion)
        # Type "a.b", readline thinks word is "b" (idx 2-3), plen is 3. offset = 3 - 1 = 2
        ("b", "a.b", 2, 3, 3, RichCompletion("a.bc", prefix_len=3), "bc", RichCompletion),
        
        # Xonsh plen < Readline plen (Pad missing prefix from buffer at front)
        # Type "a.b", readline considers whole "a.b", plen only 1
        # gap = 3 - 1 = 2 -> Add "a." to the completion
        ("a.b", "a.b", 0, 3, 1, RichCompletion("bc", prefix_len=1), "a.bc", RichCompletion),
        
        # Metadata check - Ensure append_space=True survives the slicing/padding math
        ("jso", "jso", 0, 3, 3, RichCompletion("json", prefix_len=3, append_space=True), "json", RichCompletion),
    ]
)
def test_boundary_alignment(readline_shell, monkeypatch, prefix, line, begidx, endidx, plen, mock_comp, expected_str, expected_type):
    """
    Test that boundary adjustments correctly slice or pad the returned text 
    while preserving RichCompletion objects and their metadata.
    """
    import xonsh.shells.readline_shell as rlshell
    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=2))
    
    mock_completer = MagicMock()
    mock_completer.complete.return_value = ({mock_comp}, plen)
    readline_shell.completer = mock_completer
    
    results = readline_shell.completedefault(prefix, line, begidx, endidx)
    assert len(results) == 1
    
    res = results[0]
    assert type(res) == expected_type
    assert str(res) == expected_str
    
    # If the original had append_space=True, assert the new object retained it
    if getattr(mock_comp, "append_space", False):
        assert getattr(res, "append_space", False) is True


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
