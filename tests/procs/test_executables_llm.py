"""LLM-generated tests for :mod:`xonsh.procs.executables`.

Command-name resolution parity with other shells: a name containing a path
separator is resolved against the file system (relative to the current
directory or absolute) and is never looked up in ``$PATH`` (gh-6532).
"""

import os

from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import (
    is_explicit_path,
    locate_executable,
    locate_file,
)
from xonsh.tools import chdir


def test_is_explicit_path():
    sep = os.path.sep
    # Bare names (no separator) are looked up in $PATH.
    assert not is_explicit_path("binfile")
    assert not is_explicit_path("binfile.exe")
    # Anything containing a separator is an explicit path.
    assert is_explicit_path(f".{sep}binfile")
    assert is_explicit_path(f"..{sep}binfile")
    assert is_explicit_path(f"sub{sep}binfile")
    assert is_explicit_path(f"{sep}abs{sep}binfile")
    if ON_WINDOWS:
        # On Windows both separators count.
        assert is_explicit_path("sub/binfile")
        assert is_explicit_path("sub\\binfile")


def test_locate_executable_path_like_matches_shell(tmpdir, xession):
    """Regression gh-6532: a command name containing a path separator must be
    resolved only against the file system (relative to the current directory or
    absolute) and never looked up in ``$PATH`` — matching the behaviour of
    other shells.

    Layout: an executable ``prog`` and a nested ``sub/tool`` live in a ``$PATH``
    directory; the current directory has its own ``sub/tool`` but no ``prog``.
    """
    pathdir = tmpdir.mkdir("pathdir")
    (pd_sub := pathdir.mkdir("sub"))
    cwd = tmpdir.mkdir("cwd")  # current directory WITHOUT `prog`
    cwd_sub = cwd.mkdir("sub")

    exe = "prog.EXE" if ON_WINDOWS else "prog"
    tool = "tool.EXE" if ON_WINDOWS else "tool"
    for f in (pathdir / exe, pd_sub / tool, cwd_sub / tool):
        f.write_text("binary", encoding="utf8")
        os.chmod(f, 0o777)

    pathext = [".EXE"] if ON_WINDOWS else []
    sep = os.path.sep
    with (
        xession.env.swap(PATH=[str(pathdir)], PATHEXT=pathext),
        chdir(str(cwd)),
    ):
        # Bare name -> resolved through $PATH.
        assert locate_executable(exe) is not None

        # `./prog` explicit path -> NOT in cwd -> not found, no $PATH leak.
        assert locate_executable(f".{sep}{exe}") is None
        assert locate_file(f".{sep}{exe}") is None

        # `sub/tool` (separator, no leading `./`) -> resolves against cwd, NOT $PATH.
        located = locate_executable(f"sub{sep}{tool}")
        assert located is not None
        assert str(cwd) in located and str(pathdir) not in located

        # A nested tool that exists ONLY under $PATH must NOT be found by a
        # path-like name (the shell never $PATH-searches a name with a slash).
        (pathdir.mkdir("only") / tool).write_text("binary", encoding="utf8")
        os.chmod(pathdir / "only" / tool, 0o777)
        assert locate_executable(f"only{sep}{tool}") is None
