"""Tests for path/cd completion through ``..`` segments.

The path completer routes through ``xonsh.tools._case_insensitive_iglob``
on POSIX. That helper used to walk paths segment-by-segment via
``os.listdir``, which never yields ``.`` or ``..`` — so any pattern with
a ``..`` component (``cd ../<Tab>``, ``cd ../../<Tab>``, even
``cd /tmp/../etc/<Tab>``) returned zero matches and the completer
short-circuited the entire pipeline.

The fix mirrors stdlib glob: ``.`` / ``..`` / trailing-empty segments are
treated as literal path-walking steps, not as names to look up.

Regression covered: https://github.com/xonsh/xonsh/issues/6403
"""

import os
import tempfile

import pytest

import xonsh.completers.path as xcp
from xompletions.cd import xonsh_complete as cd_xonsh_complete
from xonsh.parsers.completion_context import CommandArg, CommandContext


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


def _cd_command_ctx(prefix: str) -> CommandContext:
    """Build the CommandContext that ``cd <prefix><Tab>`` produces."""
    return CommandContext(
        args=(CommandArg(value="cd"),),
        arg_index=1,
        prefix=prefix,
    )


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_cd_dotdot_slash_lists_parent_subdirs(completer_env, monkeypatch):
    """``cd ../<Tab>`` must list the parent directory's subdirectories.

    This is the exact failure from issue #6403. Before the fix, the
    completer returned zero results and the cd-xompletion raised
    StopIteration, which broke the whole completer pipeline.
    """
    with tempfile.TemporaryDirectory() as td:
        # Layout: <td>/work/  <td>/sib1/  <td>/sib2/  <td>/file.txt
        # cwd is <td>/work, so '..' is <td> and the siblings + the
        # cwd itself are valid dir completions.
        work = os.path.join(td, "work")
        os.mkdir(work)
        os.mkdir(os.path.join(td, "sib1"))
        os.mkdir(os.path.join(td, "sib2"))
        open(os.path.join(td, "file.txt"), "w").close()
        monkeypatch.chdir(work)

        results, _ = cd_xonsh_complete(_cd_command_ctx("../"))
        basenames = {os.path.basename(str(r).rstrip().rstrip(os.sep)) for r in results}
        assert {"sib1", "sib2", "work"}.issubset(basenames)
        # Plain files in the parent must not appear — cd filters to dirs.
        assert "file.txt" not in basenames


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_cd_dotdot_dotdot_slash_lists_grandparent(completer_env, monkeypatch):
    """``cd ../../<Tab>`` walks two levels up."""
    with tempfile.TemporaryDirectory() as td:
        # Layout: <td>/a/b/  <td>/sib_of_a/
        a = os.path.join(td, "a")
        ab = os.path.join(a, "b")
        os.makedirs(ab)
        os.mkdir(os.path.join(td, "sib_of_a"))
        monkeypatch.chdir(ab)

        results, _ = cd_xonsh_complete(_cd_command_ctx("../../"))
        basenames = {os.path.basename(str(r).rstrip().rstrip(os.sep)) for r in results}
        # Both the grandparent's children must show up.
        assert {"a", "sib_of_a"}.issubset(basenames)


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_path_completer_dotdot_lists_files_too(completer_env, monkeypatch):
    """``cat ../<Tab>`` (no dir filter) must list files and directories
    in the parent. Same root cause as the cd case but exercised through
    the generic path completer used for non-cd commands."""
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, "work")
        os.mkdir(work)
        os.mkdir(os.path.join(td, "sib"))
        open(os.path.join(td, "note.txt"), "w").close()
        monkeypatch.chdir(work)

        prefix = "../"
        line = f"cat {prefix}"
        paths, _ = xcp._complete_path_raw(prefix, line, 4, len(line), {})
        basenames = {os.path.basename(str(p).rstrip().rstrip(os.sep)) for p in paths}
        # Both file and dir siblings should be offered.
        assert "sib" in basenames
        assert "note.txt" in basenames


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_cd_dotdot_in_absolute_path(completer_env, monkeypatch):
    """``cd /tmp/../<real-dir>/<Tab>`` resolves the ``..`` mid-path."""
    with tempfile.TemporaryDirectory() as td:
        # Use an absolute-path prefix that contains '..' in the middle.
        target = os.path.join(td, "target")
        os.makedirs(os.path.join(target, "child_a"))
        os.makedirs(os.path.join(target, "child_b"))
        # Path of the form '<td>/target/../target/'
        prefix = os.path.join(target, "..", "target") + os.sep

        results, _ = cd_xonsh_complete(_cd_command_ctx(prefix))
        basenames = {os.path.basename(str(r).rstrip().rstrip(os.sep)) for r in results}
        assert {"child_a", "child_b"}.issubset(basenames)


@pytest.mark.skipif(xcp.xp.ON_WINDOWS, reason="POSIX-only iglob path")
def test_cd_dotdot_does_not_break_pipeline(completer_env, monkeypatch):
    """Regression guard for the StopIteration short-circuit.

    Before the fix, when ``complete_dir`` returned an empty set the
    cd-xompletion raised ``StopIteration`` to skip the rest of the
    pipeline. With the iglob fix, ``../`` actually returns directories,
    so StopIteration is not raised and the pipeline behaves normally.
    """
    with tempfile.TemporaryDirectory() as td:
        os.mkdir(os.path.join(td, "subdir"))
        monkeypatch.chdir(td)

        # 'subdir/../' must list cwd's directories.
        results, _ = cd_xonsh_complete(_cd_command_ctx("subdir/../"))
        basenames = {os.path.basename(str(r).rstrip().rstrip(os.sep)) for r in results}
        assert "subdir" in basenames
