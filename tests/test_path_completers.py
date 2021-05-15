import pytest
from unittest.mock import patch
import tempfile
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
