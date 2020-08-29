import pytest

from xonsh.completers.tools import RichCompletion
from xonsh.readline_shell import _render_completions


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
