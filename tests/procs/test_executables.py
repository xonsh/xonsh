import os

from xonsh.environ import Env
from xonsh.platform import ON_WINDOWS
from xonsh.procs import executables as executables_mod
from xonsh.procs.executables import (
    _cached_dir_contains,
    _stable_dir_cache,
    get_paths,
    get_possible_names,
    locate_executable,
    locate_file,
    locate_relative_path,
)
from xonsh.tools import chdir


def test_get_possible_names():
    env = Env(PATHEXT=[".EXE", ".COM"])
    result = get_possible_names("file", env)
    assert result[0] == "file"
    assert "file.exe" in result
    assert "file.com" in result
    result_upper = get_possible_names("FILE", env)
    assert result_upper[0] == "FILE"
    assert "FILE.EXE" in result_upper
    assert "FILE.COM" in result_upper


def test_get_paths(tmpdir):
    bindir1 = str(tmpdir.mkdir("bindir1"))
    bindir2 = str(tmpdir.mkdir("bindir2"))
    env = Env(PATH=[bindir1, bindir2, bindir1, "nodir"])
    assert get_paths(env) == (bindir2, bindir1)


def test_locate_executable(tmpdir, xession):
    bindir0 = tmpdir.mkdir("bindir0")  # current working directory
    bindir1 = tmpdir.mkdir("bindir1")
    bindir2 = tmpdir.mkdir("bindir2")
    bindir3 = tmpdir.mkdir("bindir3")
    bindir2.mkdir("subdir")
    executables = ["file1.EXE", "file2.COM", "file2.EXE", "file3"]
    not_executables = ["file4.EXE", "file5"]
    for exefile in executables + not_executables:
        f = bindir2 / exefile
        f.write_text("binary", encoding="utf8")
        if exefile in executables:
            os.chmod(f, 0o777)

    # Test current working directory.
    (bindir0 / "cwd_non_bin_file").write_text("binary", encoding="utf8")
    (f := bindir0 / "cwd_bin_file.EXE").write_text("binary", encoding="utf8")
    os.chmod(f, 0o777)

    # Test overlapping file names in different bin directories.
    (f := bindir3 / "file3").write_text("binary", encoding="utf8")
    os.chmod(f, 0o777)

    pathext = [".EXE", ".COM"] if ON_WINDOWS else []
    sep = os.path.sep

    with (
        xession.env.swap(
            PATH=[str(bindir1), str(bindir2), str(bindir3)], PATHEXT=pathext
        ),
        chdir(str(bindir0)),
    ):
        # From current working directory
        assert locate_executable(f".{sep}cwd_non_bin_file") is None
        assert locate_executable(f".{sep}cwd_bin_file.EXE")
        assert locate_executable(f"..{sep}bindir0{sep}cwd_bin_file.EXE")
        assert locate_executable(str(bindir0 / "cwd_bin_file.EXE"))
        if ON_WINDOWS:
            assert locate_executable(f".{sep}cwd_bin_file")
            assert locate_executable(str(bindir0 / "cwd_bin_file"))
            assert locate_executable(f"..{sep}bindir0{sep}cwd_bin_file")

            # PATHEXT resolution must return the path WITH the matched extension
            # so that CreateProcess can find the file (it only auto-appends .exe)
            result = locate_executable(f".{sep}cwd_bin_file")
            assert result.endswith("cwd_bin_file.exe"), (
                f"PATHEXT resolution should include extension: {result}"
            )

        # From PATH
        assert locate_executable("file1.EXE")
        assert locate_executable("nofile") is None
        assert locate_executable("file5") is None
        assert locate_executable("subdir") is None
        if ON_WINDOWS:
            assert locate_executable("file1")
            assert locate_executable("file4")
            assert locate_executable("file2").endswith("file2.exe")
        else:
            assert locate_executable("file3").find("bindir2") > 0
            assert locate_executable("file1") is None
            assert locate_executable("file4") is None
            assert locate_executable("file2") is None


def test_locate_relative_path_returns_found_name(tmpdir, xession):
    """When PATHEXT finds a file with extension, the returned path must include that extension."""
    bindir = tmpdir.mkdir("reldir")
    # use lowercase extension: get_possible_names lowercases extensions for lowercase input
    (f := bindir / "myapp.exe").write_text("binary", encoding="utf8")
    os.chmod(f, 0o777)

    pathext = [".EXE"]
    with xession.env.swap(PATH=[], PATHEXT=pathext), chdir(str(bindir)):
        result = locate_relative_path("./myapp", use_pathext=True)
        assert result is not None
        assert os.path.basename(result) == "myapp.exe"


def test_locate_file(tmpdir, xession):
    bindir1 = tmpdir.mkdir("bindir1")
    bindir2 = tmpdir.mkdir("bindir2")
    bindir3 = tmpdir.mkdir("bindir3")
    file = bindir2 / "findme"
    file.write_text("", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir1), str(bindir2), str(bindir3)]):
        f = locate_file("findme")
        assert str(f) == str(file)


def test_stable_dir_cache(tmpdir, xession):
    """Directories in $XONSH_COMMANDS_CACHE_READ_DIR_ONCE are scanned once
    and subsequent lookups use the cached frozenset instead of stat()."""
    stable = tmpdir.mkdir("stable")
    (f := stable / "runme.EXE").write_text("binary", encoding="utf8")
    os.chmod(f, 0o777)

    pathext = [".EXE"] if ON_WINDOWS else []
    stable_str = str(stable)

    # Reset module-level cache state from previous tests
    executables_mod._stable_prefixes_source = None
    executables_mod._stable_prefixes = ()
    _stable_dir_cache.clear()
    executables_mod._stable_dir_reported.clear()

    # --- Without caching: dir is not in CACHE_READ_DIR_ONCE ---
    with xession.env.swap(
        PATH=[stable_str],
        PATHEXT=pathext,
        XONSH_COMMANDS_CACHE_READ_DIR_ONCE=[],
    ):
        result = locate_executable("runme.EXE")
        assert result is not None
        assert "runme" in result.lower()
        # _cached_dir_contains returns None for non-stable dirs
        assert _cached_dir_contains(stable_str, "runme.EXE") is None
        assert stable_str not in _stable_dir_cache

    # --- With caching: add the dir to CACHE_READ_DIR_ONCE ---
    with xession.env.swap(
        PATH=[stable_str],
        PATHEXT=pathext,
        XONSH_COMMANDS_CACHE_READ_DIR_ONCE=[stable_str],
    ):
        result = locate_executable("runme.EXE")
        assert result is not None
        assert "runme" in result.lower()
        # Dir is now cached
        assert stable_str in _stable_dir_cache
        assert "runme.exe" in _stable_dir_cache[stable_str]
        # Subsequent lookup returns from cache (found=True)
        cached = _cached_dir_contains(stable_str, "runme.EXE")
        assert cached is not None
        found, _populated = cached
        assert found is True
        # Non-existent file returns (False, ...)
        cached_miss = _cached_dir_contains(stable_str, "nope.EXE")
        assert cached_miss is not None
        assert cached_miss[0] is False


def test_stable_dir_cache_skips_directories(tmpdir, xession):
    """A directory inside a cached $PATH entry must not be returned
    by locate_executable — even when the directory has +x permission."""
    stable = tmpdir.mkdir("stable")
    # Create a subdirectory named "man" (like coreutils gnubin/man)
    stable.mkdir("man")
    # Create a real executable so the dir is not empty
    (f := stable / "ls").write_text("binary", encoding="utf8")
    os.chmod(f, 0o777)

    stable_str = str(stable)

    executables_mod._stable_prefixes_source = None
    executables_mod._stable_prefixes = ()
    _stable_dir_cache.clear()
    executables_mod._stable_dir_reported.clear()

    with xession.env.swap(
        PATH=[stable_str],
        PATHEXT=[],
        XONSH_COMMANDS_CACHE_READ_DIR_ONCE=[stable_str],
    ):
        # "man" is a directory — must not be found
        assert locate_executable("man") is None
        # "ls" is a file — must be found
        assert locate_executable("ls") is not None
