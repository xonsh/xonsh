import pytest

from xonsh.lib.string import commonprefix


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
