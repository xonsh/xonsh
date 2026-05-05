"""Tests for ``xonsh.tools._case_insensitive_iglob`` — the segment-walking
case-insensitive glob that backs path/dir/command completion on POSIX.

Coverage:
- basic relative + absolute, with and without wildcards
- case-folded basename, parent, and extension matches
- ``./`` prefix preservation
- recursive ``**`` semantics
- dotfile filtering (default vs ``include_dotfiles=True``)
- empty / nonexistent inputs
- ``PermissionError`` fallback to literal name (Android sandbox scenario)

Skipped on Windows: the helper is bypassed there in ``_iglobpath``.
"""

import os
import sys

import pytest

from xonsh.tools import _case_insensitive_iglob

skip_on_windows = pytest.mark.skipif(
    sys.platform.startswith("win"), reason="helper is POSIX-only"
)


# Detect filesystem case-sensitivity once. macOS APFS is typically
# case-insensitive at the FS level; Linux ext4/xfs/btrfs are sensitive.
@pytest.fixture(scope="module")
def case_sensitive_fs(tmp_path_factory):
    p = tmp_path_factory.mktemp("cs")
    (p / "_CaseTest").touch()
    sensitive = not (p / "_casetest").exists()
    return sensitive


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """Set up a fixed tree under tmp_path and chdir into it.

    Layout::

        Foo/bar.txt
        Foo/BAZ.MD
        README.md
        notes.md
        .hidden
        nested/sub/deep.txt
        nested/top.txt
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "bar.txt").touch()
    (tmp_path / "Foo" / "BAZ.MD").touch()
    (tmp_path / "README.md").touch()
    (tmp_path / "notes.md").touch()
    (tmp_path / ".hidden").touch()
    (tmp_path / "nested" / "sub").mkdir(parents=True)
    (tmp_path / "nested" / "sub" / "deep.txt").touch()
    (tmp_path / "nested" / "top.txt").touch()
    return tmp_path


# ---------- relative paths ----------------------------------------------


@skip_on_windows
def test_relative_exact_basename(tree):
    assert sorted(_case_insensitive_iglob("README*")) == ["README.md"]


@skip_on_windows
def test_relative_case_folded_basename(tree):
    # Different case for the basename — must still find README.md.
    assert sorted(_case_insensitive_iglob("readme*")) == ["README.md"]


@skip_on_windows
def test_relative_wildcard_extension_case_fold(tree):
    # *.MD matches *.md and *.MD alike on the basename casefold path.
    out = sorted(_case_insensitive_iglob("*.MD"))
    assert out == ["README.md", "notes.md"]


@skip_on_windows
def test_relative_dot_prefix_preserved(tree):
    # './'-prefixed input keeps the prefix in output (matches glob.iglob
    # semantics, which the path completer relies on for trailing-quote
    # handling).
    assert sorted(_case_insensitive_iglob("./readme*")) == ["./README.md"]


@skip_on_windows
def test_relative_no_dot_prefix_when_pattern_lacks_one(tree):
    # No './' in the pattern → no './' in the output, even though the
    # walker internally starts from "." for relative inputs.
    out = sorted(_case_insensitive_iglob("README*"))
    assert all(not p.startswith("./") for p in out), out


# ---------- absolute paths ---------------------------------------------


@skip_on_windows
def test_absolute_literal(tree):
    assert sorted(_case_insensitive_iglob(str(tree))) == [str(tree)]


@skip_on_windows
def test_absolute_basename_wildcard(tree):
    assert sorted(_case_insensitive_iglob(str(tree / "readme*"))) == [
        str(tree / "README.md")
    ]


@skip_on_windows
def test_absolute_case_folded_parent(tree):
    # The user typed 'foo' for a directory really named 'Foo'. Listing
    # the parent must produce on-disk casing for the matched path.
    out = sorted(_case_insensitive_iglob(str(tree / "foo" / "bar.txt")))
    assert out == [str(tree / "Foo" / "bar.txt")]


@skip_on_windows
def test_absolute_case_folded_basename_in_subdir(tree):
    # Foo/baz.md must find Foo/BAZ.MD via case-fold on the basename.
    out = sorted(_case_insensitive_iglob(str(tree / "Foo" / "baz.md")))
    assert out == [str(tree / "Foo" / "BAZ.MD")]


# ---------- empty / nonexistent ----------------------------------------


@skip_on_windows
def test_nonexistent_returns_empty(tree):
    assert list(_case_insensitive_iglob("nonexistent_xyz")) == []


@skip_on_windows
def test_empty_pattern_returns_empty():
    # Should not raise — completers may pass an empty prefix.
    assert list(_case_insensitive_iglob("")) == []


# ---------- dotfiles ---------------------------------------------------


@skip_on_windows
def test_bare_wildcard_excludes_dotfiles_by_default(tree):
    # Bare '*' (no leading '.') hides dotfiles by default — matches
    # stdlib glob with include_hidden=False.
    out = sorted(_case_insensitive_iglob("*"))
    assert ".hidden" not in out
    assert "README.md" in out


@skip_on_windows
def test_explicit_dot_wildcard_matches_dotfiles(tree):
    # A wildcard segment whose pattern starts with '.' is an explicit
    # request for hidden names, so the dotfile filter is bypassed even
    # with include_dotfiles=False. Mirrors stdlib glob, where
    # glob.glob('.*', include_hidden=False) returns dotfile entries.
    out = sorted(_case_insensitive_iglob(".*"))
    assert ".hidden" in out


@skip_on_windows
def test_literal_hidden_segment_is_traversed(tmp_path):
    # A literal segment that happens to start with '.' (no glob meta)
    # must always be traversed — otherwise paths like '~/.config/<Tab>'
    # cannot be completed without flipping a global flag.
    hidden = tmp_path / ".foo"
    hidden.mkdir()
    (hidden / "a.txt").touch()
    (hidden / "b.txt").touch()
    pattern = str(hidden / "*")
    out = sorted(_case_insensitive_iglob(pattern, include_dotfiles=False))
    assert out == [str(hidden / "a.txt"), str(hidden / "b.txt")]


@skip_on_windows
def test_dotfiles_included_when_requested(tree):
    # include_dotfiles=True shows hidden names even when the wildcard
    # itself doesn't anchor at '.'.
    out = sorted(_case_insensitive_iglob("*", include_dotfiles=True))
    assert ".hidden" in out


# ---------- recursive ** -----------------------------------------------


@skip_on_windows
def test_recursive_glob_finds_nested(tree):
    out = sorted(_case_insensitive_iglob("nested/**/*.txt", recursive=True))
    # Both the top-level top.txt and the deep one must be found.
    assert "nested/top.txt" in out
    assert os.path.join("nested", "sub", "deep.txt") in out


@skip_on_windows
def test_recursive_off_treats_double_star_as_single_segment(tree):
    # Without recursive=True, '**' degenerates to a single-segment
    # wildcard (matches one directory level), mirroring stdlib glob.
    # So nested/**/*.txt matches at one depth (nested/sub/deep.txt)
    # but does NOT also match nested/top.txt (which is one level
    # shallower than the pattern allows).
    out = sorted(_case_insensitive_iglob("nested/**/*.txt", recursive=False))
    assert out == [os.path.join("nested", "sub", "deep.txt")]


# ---------- PermissionError fallback -----------------------------------


@skip_on_windows
def test_permission_error_falls_back_to_literal(tree, mocker):
    # Simulate the Android/Termux scenario: os.listdir fails with EACCES
    # on every directory, but the literal path on disk exists. The
    # helper should yield the literal path rather than raise/swallow.
    real_listdir = os.listdir

    def listdir_perm_error(path):
        raise PermissionError(13, "Permission denied")

    mocker.patch("os.listdir", side_effect=listdir_perm_error)

    target = str(tree / "README.md")
    out = sorted(_case_insensitive_iglob(target))
    assert out == [target]
    # Sanity: the real FS does have the file, listdir is the only thing
    # we mocked away.
    assert "README.md" in real_listdir(str(tree))


@skip_on_windows
def test_permission_error_with_missing_literal_returns_empty(tree, mocker):
    # listdir denied AND the literal path doesn't exist → empty.
    mocker.patch("os.listdir", side_effect=PermissionError(13, "Permission denied"))
    out = list(_case_insensitive_iglob(str(tree / "no_such_file.xyz")))
    assert out == []


@skip_on_windows
def test_permission_error_with_wildcard_returns_empty(tree, mocker):
    # Listing failed and the segment has glob metacharacters — there is
    # no literal candidate to fall back to, so result must be empty
    # (we must not invent matches). Important: confirms we do not
    # silently leak a casefold attempt that would forge a path.
    mocker.patch("os.listdir", side_effect=PermissionError(13, "Permission denied"))
    out = list(_case_insensitive_iglob(str(tree / "Foo" / "*.txt")))
    assert out == []


# ---------- non-directory parent comes back empty ----------------------


@skip_on_windows
def test_non_directory_in_path_returns_empty(tree):
    # README.md is a regular file; treating it as a directory must not
    # error and must return empty.
    out = list(_case_insensitive_iglob(str(tree / "README.md" / "anything")))
    assert out == []


# ---------- '.' / '..' / trailing-slash navigation ---------------------
#
# os.listdir() never yields '.' or '..', so segment-by-segment walking
# would treat them as missing entries unless they are handled as literal
# path-walking segments. Same for the empty trailing segment after a
# trailing slash. These tests pin the behavior against stdlib glob.


@skip_on_windows
def test_dot_dot_wildcard_lists_parent(tree):
    # 'cd ../' expands to '../*' before reaching iglob. The walker must
    # yield the parent directory's contents — this is the regression
    # from issue #6403 where 'cd ../<Tab>' produced no completions.
    out = sorted(_case_insensitive_iglob("../*"))
    # ``tree`` is one of the entries the parent should list.
    assert os.path.join("..", tree.name) in out


@skip_on_windows
def test_dot_dot_literal_yields_parent(tree):
    # Bare '..' yields '..' (matches stdlib glob('..') == ['..']).
    assert list(_case_insensitive_iglob("..")) == [".."]


@skip_on_windows
def test_dot_dot_trailing_slash_preserves_separator(tree):
    # '../' should yield '../' (preserved trailing slash), not '..' —
    # mirroring stdlib glob and what 'cd ../' visually expects.
    assert list(_case_insensitive_iglob("../")) == [".." + os.sep]


@skip_on_windows
def test_dot_dot_in_middle_of_absolute_path(tree):
    # '..' segments mid-path must be traversed literally so callers
    # like 'cd /tmp/../etc/<Tab>' resolve through the parent.
    target = tree / "Foo" / ".." / "README.md"
    out = list(_case_insensitive_iglob(str(target)))
    assert out == [str(target)]


@skip_on_windows
def test_dot_dot_in_middle_of_relative_path(tree):
    # Relative variant: 'Foo/../README.md' walks Foo, climbs back, lands
    # on README.md. Result keeps the literal '..' (no normpath collapse)
    # to match stdlib glob.
    out = list(_case_insensitive_iglob(os.path.join("Foo", "..", "README.md")))
    assert out == [os.path.join("Foo", "..", "README.md")]


@skip_on_windows
def test_dot_dot_dot_dot_wildcard(tree):
    # Two-level climb: '../../' must reach the grandparent. Use the
    # fixture's parent's parent name as a known entry.
    grandparent = tree.parent.parent
    out = sorted(_case_insensitive_iglob("../../*"))
    # tree.parent.name is one entry in the grandparent.
    assert os.path.join("..", "..", tree.parent.name) in out
    # Also confirm grandparent matches what we computed manually.
    assert grandparent.is_dir()


@skip_on_windows
def test_trailing_slash_on_named_dir_preserves_separator(tree):
    # Standalone trailing-slash test (no '..'): 'Foo/' must yield 'Foo/'
    # rather than 'Foo'. This matches stdlib glob and avoids stripping
    # the user-typed separator in path-completion display.
    assert list(_case_insensitive_iglob("Foo/")) == ["Foo" + os.sep]


@skip_on_windows
def test_dot_dot_is_listdir_independent(tree, mocker):
    # '..' navigation must NOT depend on os.listdir of the cur path —
    # otherwise sandbox/EACCES setups would break parent traversal.
    # Listing fails everywhere; we still want '../README.md' to resolve
    # because '..' is handled literally.
    real_listdir = os.listdir
    target_parent = tree
    fake = {str(target_parent), str(target_parent / "..")}

    def listdir_selective(path):
        if str(path) in fake:
            raise PermissionError(13, "Permission denied")
        return real_listdir(path)

    mocker.patch("os.listdir", side_effect=listdir_selective)
    # 'README.md' is in tree; stepping out and back in must still find it
    # via the literal-path EACCES fallback for the README segment, while
    # the '..' segment itself never touches listdir.
    out = list(_case_insensitive_iglob(os.path.join("..", tree.name, "README.md")))
    assert out == [os.path.join("..", tree.name, "README.md")]
