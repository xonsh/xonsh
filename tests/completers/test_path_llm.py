"""Tests for ``option=value`` path completion in ``xonsh/completers/path.py``.

When an argument looks like ``--opt=/some/path`` or ``var=/some/path`` the
path completer should complete only the value after the first ``=`` while
preserving the ``opt=`` part.  A real filesystem path that itself contains
``=`` (a file/dir literally named ``qwe=asd``) must still be completed as a
whole and never split.
"""

import os
import tempfile

import pytest

import xonsh.completers.path as xcp


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


@pytest.fixture
def path_env(xession):
    xession.env = {
        "GLOB_SORTED": True,
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "SUGGEST_THRESHOLD": 3,
        "CDPATH": set(),
    }
    return xession.env


def _apply(line, result):
    """Apply each completion the way the shell does (replace the last
    ``lprefix`` chars of ``line`` with the completion) and return the lines.
    """
    comps, lprefix = result
    return sorted(line[: len(line) - lprefix] + str(c).rstrip() for c in comps)


@pytest.mark.parametrize(
    "opt",
    ["--some-dash-path", "-opt-dash-opt", "if", "--out"],
    ids=["double-dash", "single-dash", "no-dash", "short-opt"],
)
def test_option_value_completes_path_after_equals(
    opt, path_env, completion_context_parse
):
    """``app <opt>=/dir/<TAB>`` completes the path, keeping ``<opt>=``."""
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "alpha"))
        os.makedirs(os.path.join(td, "beta"))

        line = f"app {opt}={td}{os.sep}al"
        applied = _apply(
            line, xcp.complete_path(completion_context_parse(line, len(line)))
        )

        # the directory after '=' is completed ...
        assert applied == [f"app {opt}={td}{os.sep}alpha{os.sep}"]
        # ... and the 'opt=' part is preserved (lprefix covers only the value)
        assert all(a.startswith(f"app {opt}={td}{os.sep}") for a in applied)


# The cwd-relative tests below use the ``tmp_path`` fixture rather than
# ``tempfile.TemporaryDirectory``: they ``chdir`` into the directory, and on
# Windows a directory can't be removed while it is the current working
# directory.  ``TemporaryDirectory`` rmtree's on ``with`` exit — before
# ``monkeypatch`` restores the cwd — raising ``WinError 32``.  pytest cleans
# ``tmp_path`` lazily, after the cwd has been restored.
def test_option_value_empty_lists_cwd(
    path_env, completion_context_parse, tmp_path, monkeypatch
):
    """``app --out=<TAB>`` (empty value) lists the current directory."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "afile").touch()
    monkeypatch.chdir(tmp_path)

    line = "app --out="
    applied = _apply(line, xcp.complete_path(completion_context_parse(line, len(line))))

    assert f"app --out=subdir{os.sep}" in applied
    assert "app --out=afile" in applied


def test_real_dir_containing_equals_is_not_split(
    path_env, completion_context_parse, tmp_path, monkeypatch
):
    """A real directory named ``qwe=asd`` is completed whole, not split.

    ``app qwe=asd/<TAB>`` must list the contents of ``qwe=asd/`` rather than
    treating ``qwe=`` as an option and completing ``asd/`` in the cwd.
    """
    (tmp_path / "qwe=asd" / "inside1").mkdir(parents=True)
    (tmp_path / "qwe=asd" / "inside2").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    # complete inside the real 'qwe=asd' directory
    line = "app qwe=asd/"
    applied = _apply(line, xcp.complete_path(completion_context_parse(line, len(line))))
    assert applied == [
        f"app qwe=asd{os.sep}inside1{os.sep}",
        f"app qwe=asd{os.sep}inside2{os.sep}",
    ]

    # partial inside the directory
    line = "app qwe=asd/in"
    applied = _apply(line, xcp.complete_path(completion_context_parse(line, len(line))))
    assert f"app qwe=asd{os.sep}inside1{os.sep}" in applied
    assert f"app qwe=asd{os.sep}inside2{os.sep}" in applied

    # partial of the directory name itself (still contains '=')
    line = "app qwe=as"
    applied = _apply(line, xcp.complete_path(completion_context_parse(line, len(line))))
    assert f"app qwe=asd{os.sep}" in applied


def test_real_file_containing_equals_is_not_split(
    path_env, completion_context_parse, tmp_path, monkeypatch
):
    """A real file named ``qwe=asd`` completes whole from a partial name."""
    (tmp_path / "qwe=asd").touch()
    monkeypatch.chdir(tmp_path)

    line = "app qwe=as"
    applied = _apply(line, xcp.complete_path(completion_context_parse(line, len(line))))
    # completes the literal 'qwe=asd' name, not a split 'as'
    assert any(a.startswith("app qwe=asd") for a in applied)


def test_plain_path_completion_unaffected(path_env, completion_context_parse):
    """A normal path argument (no ``=``) is unchanged by the new logic."""
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "alpha"))

        line = f"app {td}{os.sep}al"
        applied = _apply(
            line, xcp.complete_path(completion_context_parse(line, len(line)))
        )
        assert applied == [f"app {td}{os.sep}alpha{os.sep}"]
