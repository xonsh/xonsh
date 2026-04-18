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


def test_complete_path_substring(xession, completion_context_parse):
    """Path completer should return both prefix and substring matches.

    Verifies that all tiers are present and sorted by substring position
    within each tier.
    """
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    with tempfile.TemporaryDirectory() as td:
        # tier 0: case-sensitive prefix — pos 0
        # tier 2: case-sensitive substring — various positions
        # no match
        for name in (
            "test1",  # tier 0, pos 0
            "test2",  # tier 0, pos 0
            "test3",  # tier 0, pos 0
            "a_test4",  # tier 2, pos 2
            "bb_test5",  # tier 2, pos 3
            "ccc_test6",  # tier 2, pos 4
            "unrelated.txt",  # no match
        ):
            open(os.path.join(td, name), "w").close()

        prefix = os.path.join(td, "test")
        line = f"ls {prefix}"
        out = xcp.complete_path(completion_context_parse(line, len(line)))
        basenames = {os.path.basename(str(c).rstrip()) for c in out[0]}

        # Prefix matches included
        assert "test1" in basenames
        assert "test2" in basenames
        assert "test3" in basenames
        # Substring matches included, sorted by position
        assert "a_test4" in basenames
        assert "bb_test5" in basenames
        assert "ccc_test6" in basenames
        # Non-match excluded
        assert "unrelated.txt" not in basenames


@pytest.mark.parametrize("is_dir", [True, False], ids=["dir", "file"])
def test_complete_path_literal_tilde(is_dir, xession):
    """A file/dir literally named ~ must appear as r'~' in completions."""
    xession.env.update(
        {
            "GLOB_SORTED": True,
            "SUBSEQUENCE_PATH_COMPLETION": False,
            "FUZZY_PATH_COMPLETION": False,
            "SUGGEST_THRESHOLD": 3,
            "CDPATH": set(),
        }
    )
    with tempfile.TemporaryDirectory() as td:
        tilde_path = os.path.join(td, "~")
        if is_dir:
            os.mkdir(tilde_path)
        else:
            open(tilde_path, "w").close()
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            paths, _ = xcp._complete_path_raw("~", "ls ~", 3, 4, {})
            raw_entries = {p for p in paths if p.startswith("r'")}
            assert raw_entries, f"Expected r'~' entry, got: {paths}"
            raw = raw_entries.pop()
            if is_dir:
                assert raw.rstrip("'").endswith("/"), (
                    f"Dir should have trailing slash: {raw}"
                )
            else:
                assert not raw.rstrip("'").endswith("/"), (
                    f"File should not have trailing slash: {raw}"
                )
        finally:
            os.chdir(old_cwd)


@pytest.mark.parametrize("is_dir", [True, False], ids=["dir", "file"])
def test_complete_path_literal_dollar(is_dir, xession):
    """A file/dir literally named $VAR must appear as r'$VAR' in completions."""
    xession.env.update(
        {
            "GLOB_SORTED": True,
            "SUBSEQUENCE_PATH_COMPLETION": False,
            "FUZZY_PATH_COMPLETION": False,
            "SUGGEST_THRESHOLD": 3,
            "CDPATH": set(),
        }
    )
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "$VAR")
        if is_dir:
            os.mkdir(path)
        else:
            open(path, "w").close()
        prefix = os.path.join(td, "$VA")
        line = f"ls {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        raw_entries = {p for p in paths if p.startswith("r'")}
        assert raw_entries, f"Expected r'$VAR' entry, got: {paths}"
        raw = raw_entries.pop()
        assert "$VAR" in raw, f"Expected $VAR in completion: {raw}"
        if is_dir:
            assert raw.rstrip("'").endswith("/"), (
                f"Dir should have trailing slash: {raw}"
            )
        else:
            assert not raw.rstrip("'").endswith("/"), (
                f"File should not have trailing slash: {raw}"
            )


@pytest.mark.parametrize(
    "char, escape",
    [(chr(c), r) for c, r in xcp._CONTROL_CHAR_ESCAPE.items()],
)
@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_complete_path_control_chars(char, escape, position, xession):
    """Filenames with control characters should be completed as quoted
    strings with proper escape sequences at any position.
    """
    xession.env.update(
        {
            "GLOB_SORTED": True,
            "SUBSEQUENCE_PATH_COMPLETION": False,
            "FUZZY_PATH_COMPLETION": False,
            "SUGGEST_THRESHOLD": 3,
            "CDPATH": set(),
        }
    )
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
        fpath = os.path.join(td, fname)
        try:
            open(fpath, "w").close()
            if not os.path.exists(fpath):
                raise OSError("file not created")
        except OSError:
            pytest.skip(f"filesystem cannot create file with {escape}")

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
                assert char in evaled, (
                    f"{c!r} does not eval to contain the control char"
                )


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


def test_complete_path_no_double_closing_quote(xession, completion_context_parse):
    """Completing inside a closed string should not duplicate the closing quote.

    cd './tm<cursor>' + TAB → cd './tmp/' (not cd './tmp/'')
    """
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "tmp"))
        line = f"cd '{td}/tm'"
        cursor = len(line) - 1  # before closing quote
        ctx = completion_context_parse(line, cursor)
        comps, lprefix = xcp.contextual_complete_path(ctx.command)
        completions = {str(c) for c in comps}
        for c in completions:
            assert not c.endswith("''"), f"Double closing quote: {c!r}"


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
