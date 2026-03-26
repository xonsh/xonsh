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
        "CASE_SENSITIVE_COMPLETIONS": False,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    xcp.complete_path(completion_context_parse("[1-0.1]", 7))


@patch("xonsh.completers.path._add_cdpaths")
def test_cd_path_no_cd(mock_add_cdpaths, xession, completion_context_parse):
    xession.env = {
        "CASE_SENSITIVE_COMPLETIONS": False,
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
        "CASE_SENSITIVE_COMPLETIONS": True,
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
        "CASE_SENSITIVE_COMPLETIONS": True,
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


def test_quote_paths_raw_string_trailing_backslash():
    """When a directory completion is inside a raw string, the trailing
    separator must not be \\ (which would make r\"path\\\" invalid).
    Use / instead."""
    paths = {"somedir"}
    with tempfile.TemporaryDirectory() as td:
        # Create a real directory so os.path.isdir returns True
        import os

        real_dir = os.path.join(td, "somedir")
        os.makedirs(real_dir)
        with patch(
            "xonsh.completers.path.XSH.expand_path",
            side_effect=lambda s: os.path.join(td, s),
        ):
            out, _ = xcp._quote_paths({"somedir"}, 'r"', '"', append_end=True)
    result = out.pop()
    # Must end with /" not \" — raw strings can't end with backslash
    assert result.endswith('/"'), f"Expected trailing '/\"' but got: {result}"
    assert not result.endswith('\\"'), f"Got invalid raw string ending: {result}"


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
            # No completion should produce an invalid raw string ending with \"
            if c.endswith(quote):
                before_quote = c[:-1]
                assert not before_quote.endswith("\\"), (
                    f"Invalid raw string completion: {c}"
                )


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
