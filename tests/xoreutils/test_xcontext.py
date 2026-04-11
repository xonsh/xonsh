"""Tests for the xcontext command helpers.

Tests that create real symlinks on the filesystem are skipped on Windows
(where symlink creation usually requires admin / Developer Mode). The
code paths they exercise are still cross-platform — on Windows the
``_has_symlink_cycle`` fallback handles loops that the stdlib
``os.path.realpath(strict=True)`` reports without a POSIX ``errno.ELOOP``.
"""

import os

from xonsh.pytest.tools import skip_if_on_windows
from xonsh.xoreutils.xcontext import (
    _has_symlink_cycle,
    _is_executable_file,
    _resolve_one,
    _resolve_path,
)


def _make_executable(path):
    """Write an empty file and give it ``+x`` for the current user."""
    path.write_text("")
    path.chmod(0o755)


def _make_unexecutable(path):
    """Write an empty file with no execute permissions."""
    path.write_text("")
    path.chmod(0o644)


# ---------------------------------------------------------------------------
# _resolve_one / _resolve_path (string and list values)
# ---------------------------------------------------------------------------


@skip_if_on_windows
def test_resolve_one_passthrough_when_disabled(tmp_path):
    """``resolve=False`` never follows symlinks. The accessibility check
    still runs, so an executable symlink target returns ``bad=False``."""
    target = tmp_path / "target"
    _make_executable(target)
    link = tmp_path / "link"
    link.symlink_to(target)

    resolved, bad = _resolve_one(str(link), resolve=False)
    assert resolved == str(link)  # not resolved
    assert bad is False  # but still passes the executable check


@skip_if_on_windows
def test_resolve_one_follows_symlink(tmp_path):
    """A non-cyclic symlink pointing at an executable file is followed to
    its real target and reported as NOT bad."""
    target = tmp_path / "target"
    _make_executable(target)
    link = tmp_path / "link"
    link.symlink_to(target)

    resolved, bad = _resolve_one(str(link), resolve=True)
    assert resolved == os.path.realpath(str(link))
    assert resolved == os.path.realpath(str(target))
    assert bad is False


def test_resolve_one_nonexistent_is_bad(tmp_path):
    """Dangling / missing paths can't be executed — bad=True."""
    missing = tmp_path / "does_not_exist"
    resolved, bad = _resolve_one(str(missing), resolve=True)
    assert resolved == os.path.realpath(str(missing))
    assert bad is True


def test_resolve_one_directory_is_bad(tmp_path):
    """A directory is not a runnable file — bad=True."""
    resolved, bad = _resolve_one(str(tmp_path), resolve=True)
    assert bad is True


@skip_if_on_windows
def test_resolve_one_not_executable_is_bad(tmp_path):
    """An existing, accessible, but non-``+x`` file is bad.

    POSIX-only: Windows has no per-file execute bit. Executability is
    determined by extension via ``PATHEXT`` and ``os.access(X_OK)`` on
    Windows is effectively always True for readable files. Windows
    coverage for the extension-based executable check lives in the
    dedicated ``_llm`` test module.
    """
    f = tmp_path / "foo.py"
    _make_unexecutable(f)
    resolved, bad = _resolve_one(str(f), resolve=True)
    assert resolved == os.path.realpath(str(f))
    assert bad is True


def test_resolve_one_main_py_is_not_bad(tmp_path):
    """``__main__.py`` is exempt from the ``+x`` check — it's a valid
    ``python -m <pkg>`` entry point that is never marked executable.
    ``xxonsh`` points at this file when xonsh is launched via
    ``python -m xonsh``, and it must not be rendered red.
    """
    pkg = tmp_path / "somepkg"
    pkg.mkdir()
    main = pkg / "__main__.py"
    _make_unexecutable(main)  # not +x, as __main__.py conventionally is

    resolved, bad = _resolve_one(str(main), resolve=True)
    assert resolved == os.path.realpath(str(main))
    assert bad is False


def test_resolve_one_missing_main_py_is_bad(tmp_path):
    """A non-existent ``__main__.py`` is still bad — the ``+x`` exemption
    only applies when the file actually exists."""
    missing = tmp_path / "nopkg" / "__main__.py"
    _, bad = _resolve_one(str(missing), resolve=True)
    assert bad is True


def test_resolve_one_executable_file_is_ok(tmp_path):
    """An existing, accessible, ``+x`` file is not bad."""
    f = tmp_path / "runnable"
    _make_executable(f)
    resolved, bad = _resolve_one(str(f), resolve=True)
    assert resolved == os.path.realpath(str(f))
    assert bad is False


@skip_if_on_windows
def test_resolve_one_not_executable_bad_even_without_resolve(tmp_path):
    """``resolve=False`` must NOT disable the accessibility / +x check —
    otherwise ``--no-resolve`` would hide broken entries from the user.
    POSIX-only — see :func:`test_resolve_one_not_executable_is_bad`.
    """
    f = tmp_path / "foo.py"
    _make_unexecutable(f)
    _, bad = _resolve_one(str(f), resolve=False)
    assert bad is True


@skip_if_on_windows
def test_resolve_one_dangling_symlink_is_bad(tmp_path):
    """A symlink whose target doesn't exist is flagged bad (missing)."""
    target = tmp_path / "does_not_exist"
    link = tmp_path / "dangling"
    link.symlink_to(target)

    _, bad = _resolve_one(str(link), resolve=True)
    assert bad is True


@skip_if_on_windows
def test_resolve_one_detects_cycle(tmp_path):
    """A symlink pair A → B → A must be flagged bad and leave the
    original path untouched so the caller can display it."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)

    resolved, bad = _resolve_one(str(a), resolve=True)
    assert bad is True
    assert resolved == str(a)  # original preserved


@skip_if_on_windows
def test_resolve_one_detects_self_cycle(tmp_path):
    """A self-loop (A → A) is also a cycle."""
    a = tmp_path / "selfloop"
    a.symlink_to(a)

    resolved, bad = _resolve_one(str(a), resolve=True)
    assert bad is True
    assert resolved == str(a)


def test_resolve_path_accepts_none():
    assert _resolve_path(None, resolve=True) == (None, False)


def test_resolve_path_accepts_non_path_list():
    """A list whose first element is not a string is returned as-is."""
    value = [object(), "-m", "pip"]
    assert _resolve_path(value, resolve=True) == (value, False)


@skip_if_on_windows
def test_resolve_path_list_with_cyclic_head(tmp_path):
    """For list values (e.g. xpip alias), only the first element is resolved.
    If it cycles, the list is kept and the bad flag is True."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)

    value = [str(a), "-m", "pip"]
    resolved, bad = _resolve_path(value, resolve=True)
    assert bad is True
    # Original head preserved so the display still works; tail unchanged.
    assert resolved == [str(a), "-m", "pip"]


@skip_if_on_windows
def test_resolve_path_list_with_good_head(tmp_path):
    """For list values with an executable head, the head is resolved in
    place and the tail is kept intact."""
    target = tmp_path / "real"
    _make_executable(target)
    link = tmp_path / "link"
    link.symlink_to(target)

    value = [str(link), "-m", "pip"]
    resolved, bad = _resolve_path(value, resolve=True)
    assert bad is False
    assert resolved[0] == os.path.realpath(str(link))
    assert resolved[1:] == ["-m", "pip"]


@skip_if_on_windows
def test_resolve_path_list_with_bad_head_not_executable(tmp_path):
    """A list whose first element points to a non-``+x`` file is flagged
    bad (no symlinks involved). POSIX-only — see
    :func:`test_resolve_one_not_executable_is_bad`.
    """
    f = tmp_path / "foo.py"
    _make_unexecutable(f)
    value = [str(f), "-m", "pip"]
    resolved, bad = _resolve_path(value, resolve=True)
    assert bad is True
    assert resolved == [os.path.realpath(str(f)), "-m", "pip"]


# ---------------------------------------------------------------------------
# _is_executable_file — direct unit tests for the accessibility check
# ---------------------------------------------------------------------------


def test_is_executable_file_none():
    assert _is_executable_file(None) is False
    assert _is_executable_file("") is False


def test_is_executable_file_missing(tmp_path):
    assert _is_executable_file(str(tmp_path / "nope")) is False


def test_is_executable_file_directory(tmp_path):
    assert _is_executable_file(str(tmp_path)) is False


@skip_if_on_windows
def test_is_executable_file_plain_file(tmp_path):
    """POSIX-only — see :func:`test_resolve_one_not_executable_is_bad`
    for why the ``+x``-based tests cannot run on Windows.
    """
    f = tmp_path / "plain.txt"
    _make_unexecutable(f)
    assert _is_executable_file(str(f)) is False


@skip_if_on_windows
def test_is_executable_file_executable_file(tmp_path):
    f = tmp_path / "runnable"
    _make_executable(f)
    assert _is_executable_file(str(f)) is True


def test_is_executable_file_main_py_exempt(tmp_path):
    """``__main__.py`` is treated as good regardless of ``+x`` bit."""
    pkg = tmp_path / "somepkg"
    pkg.mkdir()
    main = pkg / "__main__.py"
    _make_unexecutable(main)
    assert _is_executable_file(str(main)) is True


def test_is_executable_file_main_py_missing(tmp_path):
    """Exemption only applies to files that actually exist."""
    missing = tmp_path / "nowhere" / "__main__.py"
    assert _is_executable_file(str(missing)) is False


# ---------------------------------------------------------------------------
# _has_symlink_cycle — direct unit tests for the fallback detector
# ---------------------------------------------------------------------------


@skip_if_on_windows
def test_has_symlink_cycle_on_cycle(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)
    assert _has_symlink_cycle(str(a)) is True
    assert _has_symlink_cycle(str(b)) is True


@skip_if_on_windows
def test_has_symlink_cycle_on_valid_chain(tmp_path):
    """A → B → C (real file) is NOT a cycle."""
    c = tmp_path / "c"
    c.write_text("")
    b = tmp_path / "b"
    b.symlink_to(c)
    a = tmp_path / "a"
    a.symlink_to(b)
    assert _has_symlink_cycle(str(a)) is False


def test_has_symlink_cycle_on_plain_file(tmp_path):
    f = tmp_path / "plain"
    f.write_text("")
    assert _has_symlink_cycle(str(f)) is False


def test_has_symlink_cycle_on_nonexistent(tmp_path):
    """Missing path is not a cycle — we return False and the caller falls
    back to lenient realpath."""
    assert _has_symlink_cycle(str(tmp_path / "nope")) is False
