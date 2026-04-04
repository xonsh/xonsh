import pytest

from xonsh.completers.tools import RichCompletion
from xonsh.shells.readline_shell import _render_completions


@pytest.mark.parametrize(
    "prefix, completion, prefix_len, readline_completion",
    [
        ("", "a", 0, "a"),
        ("a", "b", 0, "ab"),
        ("a", "b", 1, "b"),
        ("adc", "bc", 2, "abc"),
        ("", RichCompletion("x", 0), 0, "x"),
        ("", RichCompletion("x", 0, "aaa", "aaa"), 0, "x"),
        ("a", RichCompletion("b", 1), 0, "b"),
        ("a", RichCompletion("b", 0), 1, "ab"),
        ("a", RichCompletion("b"), 0, "ab"),
        ("a", RichCompletion("b"), 1, "b"),
    ],
)
def test_render_completions(prefix, completion, prefix_len, readline_completion):
    assert _render_completions({completion}, prefix, prefix_len) == [
        readline_completion
    ]


def test_render_completions_filters_substring_matches():
    """Substring matches that would shrink readline's GCP must be filtered out.

    Regression test for https://github.com/xonsh/xonsh/issues/6209
    e.g. typing '@.imp.jso<Tab>' should not shrink to '@.imp.' because
    '_json' (a substring match) has a different prefix than 'json'.
    """
    prefix = "@.imp.jso"
    plen = 3  # replace last 3 chars ("jso")
    completions = {"json", "jsonrpc", "_json"}
    rendered = _render_completions(completions, prefix, plen)
    # _json renders to @.imp._json which does NOT start with @.imp.jso
    safe = [c for c in rendered if c.startswith(prefix)]
    assert all(c.startswith(prefix) for c in safe)
    assert "@.imp._json" not in safe
    assert "@.imp.json" in safe


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
