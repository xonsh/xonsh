import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import xonsh.completers.path as xcp
from xonsh.pytest.tools import skip_if_on_windows


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


@skip_if_on_windows
def test_complete_path_strip_check(xession, completion_context_parse):
    xession.env = {
        "CASE_SENSITIVE_COMPLETIONS": True,
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 1,
        "CDPATH": set(),
    }

    with tempfile.TemporaryDirectory() as tmp:
        name_newline = "newline\n"
        (Path(tmp) / name_newline).touch()

        name_space = "space "
        (Path(tmp) / name_space).touch()

        prefix = str(Path(tmp) / "new")
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        completions = {
            c.value if isinstance(c, xcp.RichCompletion) else c for c in out[0]
        }

        print(f"DEBUG Newline: {completions}")
        assert any(name_newline in c for c in completions), (
            f"Expected filename with trailing newline, got: {completions}"
        )

        prefix = str(Path(tmp) / "spa")
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        completions = {
            c.value if isinstance(c, xcp.RichCompletion) else c for c in out[0]
        }

        print(f"DEBUG Space: {completions}")
        assert any(name_space in c for c in completions), (
            f"Expected filename with trailing space, got: {completions}"
        )
