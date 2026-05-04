"""Tests for path completion through hidden (``.``-prefixed) segments.

The path completer routes through ``xonsh.tools._case_insensitive_iglob``
on POSIX. That helper used to filter out *every* listdir entry whose name
started with ``.`` — including segments the user had typed literally —
so ``cp ~/.xsh/<Tab>`` and ``cp ~/.xs<Tab>`` returned no completions.

The fix mirrors stdlib glob: a segment that *itself* starts with ``.`` is
an explicit request for a hidden name, so the dotfile filter is bypassed
for that segment regardless of ``$DOTGLOB``. Bare wildcards (``*``,
``foo*``, ``**``) still hide dotfiles unless ``$DOTGLOB=True``.
"""

import os
import tempfile

import pytest

import xonsh.completers.path as xcp


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xession, xonsh_execer):
    return xonsh_execer


@pytest.fixture
def completer_env(xession):
    xession.env.update(
        {
            "GLOB_SORTED": True,
            "SUBSEQUENCE_PATH_COMPLETION": False,
            "FUZZY_PATH_COMPLETION": False,
            "SUGGEST_THRESHOLD": 3,
            "CDPATH": set(),
            "DOTGLOB": False,
            "XONSH_COMPLETER_MODE": "substring_tier",
        }
    )
    return xession.env


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_completer_descends_through_literal_hidden_segment(completer_env):
    """``cp <tmp>/.xsh/<Tab>`` returns the directory's contents even with
    ``$DOTGLOB=False``.  The literal ``.xsh`` segment must always be
    traversed, since the user typed it explicitly."""
    with tempfile.TemporaryDirectory() as td:
        hidden = os.path.join(td, ".xsh")
        os.mkdir(hidden)
        for name in ("a.xsh", "b.xsh", "c.xsh"):
            open(os.path.join(hidden, name), "w").close()

        prefix = hidden + os.sep
        line = f"cp {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        basenames = {os.path.basename(str(p).rstrip()) for p in paths}
        assert basenames == {"a.xsh", "b.xsh", "c.xsh"}


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_completer_completes_hidden_prefix(completer_env):
    """``cp <tmp>/.xs<Tab>`` finds ``.xsh`` even with ``$DOTGLOB=False``.
    The wildcard pattern starts with ``.`` so dotfiles are visible."""
    with tempfile.TemporaryDirectory() as td:
        os.mkdir(os.path.join(td, ".xsh"))
        os.mkdir(os.path.join(td, ".xonshrc.d"))
        open(os.path.join(td, "visible.txt"), "w").close()

        prefix = os.path.join(td, ".xs")
        line = f"cp {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        basenames = {os.path.basename(str(p).rstrip().rstrip(os.sep)) for p in paths}
        # Both hidden entries with the .xs prefix should be suggested.
        assert ".xsh" in basenames
        # The non-hidden file does not match the .xs prefix at all.
        assert "visible.txt" not in basenames


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_completer_bare_wildcard_still_hides_dotfiles(completer_env):
    """``cp <tmp>/<Tab>`` (no leading dot) keeps the existing behavior:
    dotfiles in the target directory are hidden when ``$DOTGLOB=False``,
    shown when ``$DOTGLOB=True``. Confirms the fix did not change the
    bare-wildcard semantics."""
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, ".secret"), "w").close()
        open(os.path.join(td, "visible"), "w").close()

        prefix = td + os.sep
        line = f"cp {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        basenames = {os.path.basename(str(p).rstrip()) for p in paths}
        assert "visible" in basenames
        assert ".secret" not in basenames

        completer_env["DOTGLOB"] = True
        paths, _ = xcp._complete_path_raw(prefix, line, 3, len(line), {})
        basenames = {os.path.basename(str(p).rstrip()) for p in paths}
        assert ".secret" in basenames
