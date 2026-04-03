import pytest
from unittest.mock import MagicMock

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


def test_completedefault_preserves_prefix(readline_shell):
    """Completions must include the full prefix so readline does not strip it.

    Regression test for https://github.com/xonsh/xonsh/issues/6209:
    typing ``@.imp.jso<Tab>`` was collapsing to ``@.imp.`` because
    ``completedefault`` returned raw (prefix-free) completions when
    ``_querycompletions`` returned 2.
    """
    shell = readline_shell
    # Simulate what xonsh's completer returns for "@.imp.jso":
    # the raw suffix completions plus plen=3 (length of "jso").
    raw_completions = ["json", "json_decoder"]
    shell.completer = MagicMock()
    shell.completer.complete.return_value = (raw_completions, 3)

    prefix = "@.imp.jso"
    result = shell.completedefault(prefix, prefix, 0, len(prefix))

    # Every returned completion must start with the preserved prefix part.
    for comp in result:
        assert comp.startswith("@.imp."), (
            f"completion {comp!r} lost the '@.imp.' prefix"
        )


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
