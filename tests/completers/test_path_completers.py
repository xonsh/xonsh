import os
import tempfile
from unittest.mock import patch

import pytest

import xonsh.completers.path as xcp


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


def test_pattern_need_quotes():
    # just make sure the regex compiles
    xcp.PATTERN_NEED_QUOTES.match("")


def test_complete_path(xession, completion_context_parse):
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    xcp.complete_path(completion_context_parse("[1-0.1]", 7))


@pytest.mark.parametrize(
    "char, escape",
    [
        ("\n", "\\n"),
        ("\t", "\\t"),
        ("\r", "\\r"),
    ],
)
@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_complete_path_control_chars(char, escape, position, xession):
    """Filenames with control characters should be completed as quoted
    strings with proper escape sequences at any position.
    """
    xession.env.update({
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    })
    with tempfile.TemporaryDirectory() as td:
        if position == "start":
            fname = f"{char}file_ctrl"
            search = f"{char}file"
        elif position == "middle":
            fname = f"ctrl{char}file"
            search = "ctrl"
        else:
            fname = f"ctrl_file{char}"
            search = "ctrl"
        try:
            open(os.path.join(td, fname), "w").close()
        except OSError:
            pytest.skip(f"filesystem cannot create file with {escape!r}")

        prefix = os.path.join(td, search)
        line = f"ls {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        completions = {str(c).rstrip() for c in paths}
        assert any(escape in c for c in completions), (
            f"No completion with {escape!r} for position={position}: {completions}"
        )
        for c in completions:
            if escape in c:
                evaled = eval(c)
                assert char in evaled, f"{c!r} does not eval to contain the control char"


@patch("xonsh.completers.path._add_cdpaths")
def test_cd_path_no_cd(mock_add_cdpaths, xession, completion_context_parse):
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": ["/"],
    }
    xcp.complete_path(completion_context_parse("cat a", 5))
    mock_add_cdpaths.assert_not_called()


@pytest.mark.parametrize("quote", ('"', "'"))
def test_complete_path_when_prefix_is_raw_path_string(
    quote, xession, completion_context_parse
):
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 1,
        "CDPATH": set(),
    }
    with tempfile.NamedTemporaryFile(suffix="_dummySuffix") as tmp:
        prefix_file_name = tmp.name.replace("_dummySuffix", "")
        prefix = f"pr{quote}{prefix_file_name}"
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        expected = f"pr{quote}{tmp.name}{quote}"
        assert expected == out[0].pop()


def test_complete_path_ending_with_equal_sign(xession, completion_context_parse):
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 1,
        "CDPATH": set(),
    }
    with tempfile.NamedTemporaryFile(suffix="=") as tmp:
        prefix_file_name = tmp.name.replace("=", "")
        prefix = prefix_file_name
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        expected = f"{tmp.name} "  # has trailing space
        assert expected == out[0].pop()


@pytest.mark.parametrize("prefix", ("", "r", "p", "pr", "rp"))
def test_path_from_partial_string(prefix):
    string = "hello"
    quote = "'"
    out = xcp._path_from_partial_string(f"{prefix}{quote}{string}{quote}")
    if "r" in prefix:
        expected = (f"r{quote}{string}{quote}", string, f"{prefix}{quote}", quote)
    else:
        expected = (f"{quote}{string}{quote}", string, f"{prefix}{quote}", quote)
    assert out == expected


@pytest.mark.parametrize("quote", ('"', "'"))
def test_path_from_partial_string_raw_trailing_backslash(quote):
    """Raw strings can't end with \\, but _path_from_partial_string should
    still extract the path by falling back to direct extraction."""
    # Partial (unclosed) raw string ending with backslash
    inp = f"r{quote}C:\\App\\x\\"
    out = xcp._path_from_partial_string(inp)
    assert out is not None
    assert out[1] == "C:\\App\\x\\"  # extracted path value


def test_quote_paths_uppercase_raw_prefix():
    """Uppercase R prefix (R'...') should not get an extra r prepended."""
    out, _ = xcp._quote_paths({r"c:\dir1"}, "R'", "'", append_end=True)
    result = out.pop()
    assert result.startswith("R'"), f"Expected R' prefix but got: {result}"


@pytest.mark.skipif(os.sep != "\\", reason="Backslash separator is Windows-only")
def test_quote_paths_raw_string_trailing_backslash():
    """When a directory completion is inside a raw string, the trailing
    backslash is doubled so the string stays valid (r"path\\")."""
    with tempfile.TemporaryDirectory() as td:
        real_dir = os.path.join(td, "somedir")
        os.makedirs(real_dir)
        with patch(
            "xonsh.completers.path.XSH.expand_path",
            side_effect=lambda s: os.path.join(td, s),
        ):
            out, _ = xcp._quote_paths({"somedir"}, 'r"', '"', append_end=True)
    result = out.pop()
    # Must end with \\" — doubled backslash keeps raw string valid
    assert result.endswith('\\\\"'), f"Expected trailing '\\\\.\"' but got: {result}"


@pytest.mark.parametrize("quote", ('"', "'"))
def test_complete_path_raw_string_with_backslash(
    quote, xession, completion_context_parse
):
    """End-to-end: completing r\"<partial_path_with_backslash>\" should
    return valid completions, not break."""
    xession.env = {
        "CASE_SENSITIVE_COMPLETIONS": True,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 1,
        "CDPATH": set(),
    }
    with tempfile.TemporaryDirectory() as td:
        import os

        os.makedirs(os.path.join(td, "sub"))
        # Use forward slashes up to the last component, then trailing backslash
        td_fwd = td.replace("\\", "/")
        prefix = f"r{quote}{td_fwd}/"
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        completions = out[0] if out else set()
        assert len(completions) > 0, "Expected at least one completion"
        for c in completions:
            # A raw string ending with an odd number of backslashes before
            # the closing quote is invalid (the last \ escapes the quote).
            # Doubled backslash (\\) before the quote is fine.
            if c.endswith(quote):
                before_quote = c[:-1]
                trailing = len(before_quote) - len(before_quote.rstrip("\\"))
                assert trailing % 2 == 0, (
                    f"Invalid raw string completion (odd trailing backslashes): {c}"
                )


@pytest.mark.skipif(os.sep != "\\", reason="Backslash separator is Windows-only")
def test_empty_dir_no_spurious_completion(xession):
    """Completing inside an empty directory should return nothing, not a
    spurious root-path completion caused by subsequence matching."""
    xession.env = {
        "CASE_SENSITIVE_COMPLETIONS": True,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": True,
        "FUZZY_PATH_COMPLETION": True,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    with tempfile.TemporaryDirectory() as td:
        import os

        os.makedirs(os.path.join(td, "aaa", "1"))  # empty dir
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            # Simulate second Tab on r'aaa\1\\' (closed raw string, empty dir)
            pfx = "r'" + os.sep.join(["aaa", "1"]) + os.sep * 2 + "'"
            out, _ = xcp._complete_path_raw(pfx, pfx, 0, len(pfx), ctx={})
            assert len(out) == 0, f"Expected no completions for empty dir, got: {out}"
        finally:
            os.chdir(old_cwd)


@pytest.mark.parametrize("num_args", (0, 1, 2, 3))
def test_path_in_python_code(num_args, completion_context_parse):
    with tempfile.NamedTemporaryFile(prefix="long_name") as tmp:
        args = []
        if num_args:
            args = ["blah"] * 3 + [tmp.name[:-2]]
            args = args[-num_args:]

        inner_line = " ".join(map(repr, args))
        exp = xcp.complete_path(completion_context_parse(inner_line, len(inner_line)))
        line = "@(" + inner_line
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        assert out == exp


@pytest.mark.parametrize(
    "ref, typed, expected",
    [
        ("abcdef", "ace", True),
        ("abcdef", "afc", False),
        ("abcdef", "", True),
        ("", "a", False),
        ("abc", "abc", True),
        ("abc", "abcd", False),
    ],
)
def test_subsequence_match_iter(ref, typed, expected):
    assert xcp._subsequence_match_iter(ref, typed) == expected


def test_subsequence_match_iter_long_string():
    """Must not hit recursion limit on long inputs."""
    assert xcp._subsequence_match_iter("a" * 5000, "a" * 2500)
