import pytest

from xonsh.lib.string import (
    commonprefix,
    is_balanced,
    subexpr_before_unbalanced,
    subexpr_from_unbalanced,
)


@pytest.mark.parametrize(
    "strings, expected_prefix",
    [
        ([], ""),
        (["ab", "cd"], ""),
        (["ls"], "ls"),
        (["xonsh", "xonfig", "xontrib"], "xon"),
        (["a", "ab"], "a"),
        (["ab", "ab"], "ab"),
        (["python3", "python3.13"], "python3"),
    ],
)
def test_commonprefix(strings: list[str], expected_prefix: str):
    prefix = commonprefix(strings)
    length = len(prefix)
    assert prefix == expected_prefix
    # property tests (only make sense for non-empty strings):
    if not strings:
        return
    # order shouldnt matter
    assert commonprefix(strings[::-1]) == prefix
    # is a common prefix
    assert all(string.startswith(prefix) for string in strings)
    # since it is the longest, it should not be possible to extend it
    if all(len(string) > length for string in strings):  # more characters left
        assert len({string[length] for string in strings}) > 1  # not common


@pytest.mark.parametrize("inp", ["f(1,10),x.y"])
def test_is_balanced_parens(inp):
    obs = is_balanced(inp, "(", ")")
    assert obs


@pytest.mark.parametrize("inp", ["f(x.", "f(1,x.f((1,10),x.y"])
def test_is_not_balanced_parens(inp):
    obs = is_balanced(inp, "(", ")")
    assert not obs


@pytest.mark.parametrize(
    "inp, exp", [("f(x.", "x."), ("f(1,x.", "x."), ("f((1,10),x.y", "x.y")]
)
def test_subexpr_from_unbalanced_parens(inp, exp):
    obs = subexpr_from_unbalanced(inp, "(", ")")
    assert exp == obs


@pytest.mark.parametrize(
    "inp, ltok, rtok, exp",
    [
        ("d[x.", "[", "]", "x."),
        ("d[1:x.", "[", "]", "x."),
        ("{1: x.", "{", "}", " x."),
        ("[x.y]", "[", "]", "[x.y]"),
    ],
)
def test_subexpr_from_unbalanced_brackets(inp, ltok, rtok, exp):
    assert subexpr_from_unbalanced(inp, ltok, rtok) == exp


@pytest.mark.parametrize(
    "inp, exp",
    [
        ("f(x.", "f"),
        ("f(1,x.", "f"),
        ("f((1,10),x.y", "f"),
        ("wakka().f((1,10),x.y", ".f"),
        ("wakka(f((1,10),x.y", "f"),
        ("wakka(jawakka().f((1,10),x.y", ".f"),
        ("wakka(jawakka().f((1,10),x.y)", "wakka"),
    ],
)
def test_subexpr_before_unbalanced_parens(inp, exp):
    obs = subexpr_before_unbalanced(inp, "(", ")")
    assert exp == obs
