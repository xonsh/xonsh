from unittest.mock import MagicMock

import pytest

from xonsh.completers.tools import RichCompletion


def test_completedefault_substring_safety(readline_shell, monkeypatch):
    """
    Test that completedefault allows substring matches if they do not
    shrink the readline prefix (safe expansion). If multiple substring matches
    diverge and would cause the common prefix to shrink below the user's
    typed length (swallowing), it falls back to prefix-only filtering.
    """
    import xonsh.shells.readline_shell as rlshell

    monkeypatch.setattr(rlshell, "rl_completion_suppress_append", MagicMock())
    monkeypatch.setattr(rlshell, "_rebind_case_sensitive_completions", MagicMock())
    monkeypatch.setattr(rlshell, "rl_completion_query_items", MagicMock())
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=2))

    mock_completer = MagicMock()
    readline_shell.completer = mock_completer

    # -- SCENARIO 1: Safe Substring (Single candidate expands the word) --
    mock_completer.complete.return_value = (
        {RichCompletion("detect_encoding", prefix_len=3)},
        3,
    )
    # User types "enc" -> len 3
    results = readline_shell.completedefault("enc", "enc", 0, 3)
    result_strs = [str(r) for r in results]
    assert result_strs == ["detect_encoding"], (
        "Safe substring expansion should be allowed"
    )

    # -- SCENARIO 2: Safe Substring (Multiple candidates, long common prefix) --
    mock_completer.complete.return_value = (
        {
            RichCompletion("detect_encoding", prefix_len=3),
            RichCompletion("detect_encoder", prefix_len=3),
        },
        3,
    )
    results = readline_shell.completedefault("enc", "enc", 0, 3)
    result_strs = [str(r) for r in results]
    assert "detect_encoding" in result_strs
    assert "detect_encoder" in result_strs
    assert len(result_strs) == 2, (
        "Should allow multiple if common prefix >= readline_plen"
    )

    # -- SCENARIO 3: DANGEROUS Substring (Multiple candidates, short common prefix) --
    # User types "enc" (len 3). Candidates have common prefix "" (len 0).
    # 0 < 3, so readline would swallow "enc" into "".
    # Fallback to prefix matching should activate and filter to prefix candidates.
    mock_completer.complete.return_value = (
        {
            RichCompletion("encode_this", prefix_len=3),
            RichCompletion("detect_encoding", prefix_len=3),
            RichCompletion("JSONEncoder", prefix_len=3),
        },
        3,
    )
    results = readline_shell.completedefault("enc", "enc", 0, 3)
    result_strs = [str(r) for r in results]

    # "encode_this" starts with "enc". The others do not.
    # The fallback should prune the dangerous substrings and keep the safe prefix match.
    assert "encode_this" in result_strs
    assert "detect_encoding" not in result_strs
    assert "JSONEncoder" not in result_strs
    assert len(result_strs) == 1

    # -- SCENARIO 4: show_completions == 2 returns orig_completions (raw output) --
    # With show_completions==2, completedefault must return the raw completer output,
    # not the boundary-aligned rtn_completions. We verify the returned objects
    # are still RichCompletion instances (not plain strings).
    monkeypatch.setattr(readline_shell, "_querycompletions", MagicMock(return_value=2))
    comp = RichCompletion("json", prefix_len=3)
    mock_completer.complete.return_value = ({comp}, 3)
    results = readline_shell.completedefault("jso", "jso", 0, 3)
    assert len(results) == 1
    assert isinstance(results[0], RichCompletion), (
        "show_completions==2 must return orig_completions, which are RichCompletion objects"
    )


@pytest.mark.parametrize(
    "prefix, line, begidx, endidx, plen, mock_comp, expected_str, expected_type",
    [
        # Xonsh plen == Readline plen (No offset/pad, just match check)
        (
            "jso",
            "jso",
            0,
            3,
            3,
            RichCompletion("json", prefix_len=3),
            "json",
            RichCompletion,
        ),
        # Xonsh plen > Readline plen (Trim offset from front of completion)
        # Type "a.b", readline thinks word is "b" (begidx=2, endidx=3), plen=3, offset=2
        # show_completions==2 returns orig_completions (raw), so expected is original value
        (
            "b",
            "a.b",
            2,
            3,
            3,
            RichCompletion("a.bc", prefix_len=3),
            "a.bc",  # path 2 returns raw original, not trimmed
            RichCompletion,
        ),
        # Xonsh plen < Readline plen (Pad missing prefix from buffer at front)
        # Type "a.b", readline considers whole "a.b", plen only 1
        # show_completions==2 returns orig_completions (raw), so expected is original value
        (
            "a.b",
            "a.b",
            0,
            3,
            1,
            RichCompletion("bc", prefix_len=1),
            "bc",  # path 2 returns raw original, not padded
            RichCompletion,
        ),
        # Metadata check - Ensure append_space=True survives the slicing/padding math
        (
            "jso",
            "jso",
            0,
            3,
            3,
            RichCompletion("json", prefix_len=3, append_space=True),
            "json",
            RichCompletion,
        ),
        # Plain string completion (not RichCompletion) — must pass through as plain str
        (
            "jso",
            "jso",
            0,
            3,
            3,
            "json",  # plain string, no prefix_len attribute
            "json",
            str,
        ),
        # RichCompletion with prefix_len=None — should fall back to plen
        (
            "jso",
            "jso",
            0,
            3,
            3,
            RichCompletion("json", prefix_len=None),
            "json",
            RichCompletion,
        ),
        # Empty prefix — begidx == endidx, readline_plen is 0
        (
            "",
            "jso",
            3,  # begidx == endidx == 3
            3,
            0,
            RichCompletion("json", prefix_len=0),
            "json",
            RichCompletion,
        ),
    ],
)
def test_boundary_alignment(
    readline_shell,
    monkeypatch,
    prefix,
    line,
    begidx,
    endidx,
    plen,
    mock_comp,
    expected_str,
    expected_type,
):
    """
    Test that boundary adjustments correctly slice or pad the returned text
    while preserving RichCompletion objects and their metadata.
    show_completions==2 returns orig_completions (raw completer output),
    so expected_str reflects the original unmodified value.
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
    assert isinstance(res, expected_type)
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
