import os

from xonsh.environ import Env
from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import (
    get_paths,
    get_possible_names,
    locate_executable,
    locate_file,
)
from xonsh.tools import chdir


def test_get_possible_names():
    env = Env(PATHEXT=[".EXE", ".COM"])
    assert get_possible_names("file", env) == ["file", "file.exe", "file.com"]
    assert get_possible_names("FILE", env) == ["FILE", "FILE.EXE", "FILE.COM"]


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


def test_locate_file(tmpdir, xession):
    bindir1 = tmpdir.mkdir("bindir1")
    bindir2 = tmpdir.mkdir("bindir2")
    bindir3 = tmpdir.mkdir("bindir3")
    file = bindir2 / "findme"
    file.write_text("", encoding="utf8")
    with xession.env.swap(PATH=[str(bindir1), str(bindir2), str(bindir3)]):
        f = locate_file("findme")
        assert str(f) == str(file)


def test_locate_file_clean_path_cache_time(tmpdir, xession):
    # check that subsequent calls to locate_executable run faster due to use of path cache
    # that skips doing IO calls to check that path dirs exist
    from math import pow
    from time import monotonic_ns as ttime

    ns = pow(10, 9)  # nanosecond, which 'monotonic_ns' are measured in
    t0 = ttime()
    _f = locate_executable("nothing")
    t1 = ttime()
    dur1 = (t1 - t0) / ns
    t0 = ttime()
    iters = 100
    for _i in range(iters):
        _f = locate_executable("nothing")
    t1 = ttime()
    dur2 = (t1 - t0) / iters / ns
    env = xession.env
    env_path = env.get("PATH", [])
    if env_path and dur1 > 0:
        print("$PATH length = ", len(env_path))
        print(f"t1 (no cache) = {dur1:.6f}\nt2 (   cache) = {dur2:.6f}")
        assert (
            dur2 < 0.90 * dur1
        )  # 2nd+ run with cache should always be noticeable faster


def test_xonsh_dir_cache_to_list(tmpdir, xession):
    # check that adding smaller dirs to a XONSH_DIR_CACHE_TO_LIST var to list them
    # instead of checking for the existence of every file.pathext
    # is faster
    if not ON_WINDOWS:
        return

    from os import walk

    from xonsh.procs.executables import PathCache

    # create a list of smaller dirs in PATH
    short_path = 50  # exact threshold depends on the number of pathext, this is very ~
    env = xession.env
    env_path = env.get("PATH", [])
    pathext = [
        ".COM",
        ".EXE",
        ".BAT",
        ".CMD",
        ".VBS",
        ".VBE",
        ".JS",
        ".JSE",
        ".WSF",
        ".WSH",
        ".MSC",
        ".PY",
        ".PYW",
        ".XSH",
    ]
    env["PATHEXT"] = pathext

    if len(pathext) <= 2:
        print(
            f"pathext is too short {len(pathext)} for direct listing of dirs to be faster"
        )
        return

    xonsh_dir_cache_to_list = []
    for path in env_path:
        f = []
        for _dirpath, _dirnames, filenames in walk(path):
            f.extend(filenames)
            break
        if len(f) < short_path:
            xonsh_dir_cache_to_list += [path.rstrip(os.path.sep)]

    from math import pow
    from time import monotonic_ns as ttime

    ns = pow(10, 9)  # nanosecond, which 'monotonic_ns' are measured in

    env["XONSH_DIR_CACHE_TO_LIST"] = set()
    t0 = ttime()
    for _i in range(100):
        f = locate_executable("nothing")
    t1 = ttime()
    dur1 = (t1 - t0) / ns

    env["XONSH_DIR_CACHE_TO_LIST"] = xonsh_dir_cache_to_list
    PathCache.reset()  # previous benchmark set our singleton with an empty DIR_CACHE
    t0 = ttime()
    for _i in range(100):
        f = locate_executable("nothing")
    t1 = ttime()
    dur2 = (t1 - t0) / ns

    print(
        f"{len(pathext)} file.exists checks; {len(xonsh_dir_cache_to_list)} paths with <{short_path} items from ∑{len(env_path)}"
    )
    print(f"🕐{dur1:.6f}\t(file.ext)\n🕐{dur2:.6f}\t(list small dirs)\t")
    assert dur2 < 0.90 * dur1  # listing method should be noticeable faster


def test_xonsh_dir_session_cache(tmpdir, xession):
    # check that adding dirs to a XONSH_DIR_SESSION_CACHE var to cache a list of files in
    # them per session instead of checking for the existence of every file.pathext
    # is faster
    if not ON_WINDOWS:  # other OS use this for syntax checking benefit, not speed
        return

    from os import walk

    from xonsh.procs.executables import PathCache

    xonsh_dir_session_cache = []
    env = xession.env
    pathext = [
        ".COM",
        ".EXE",
        ".BAT",
        ".CMD",
        ".VBS",
        ".VBE",
        ".JS",
        ".JSE",
        ".WSF",
        ".WSH",
        ".MSC",
        ".PY",
        ".PYW",
        ".XSH",
    ]
    env["PATHEXT"] = pathext
    env_path = env.get("PATH", [])
    for path in env_path:  # cache all dirs in path
        f = []
        for _dirpath, _dirnames, filenames in walk(path):
            f.extend(filenames)
            break
        xonsh_dir_session_cache += [path.rstrip(os.path.sep)]

    from math import pow
    from time import monotonic_ns as ttime

    ns = pow(10, 9)  # nanosecond, which 'monotonic_ns' are measured in

    env["XONSH_DIR_SESSION_CACHE"] = set()
    t0 = ttime()
    for _i in range(100):
        f = locate_executable("nothing", use_dir_cache_session=True)
    t1 = ttime()
    dur1 = (t1 - t0) / ns

    env["XONSH_DIR_SESSION_CACHE"] = xonsh_dir_session_cache
    PathCache.reset()  # previous benchmark set our singleton with an empty DIR_CACHE
    f = locate_executable("nothing")  # to cache dirs
    t0 = ttime()
    for _i in range(100):
        f = locate_executable("nothing", use_dir_cache_session=True)
    t1 = ttime()
    dur2 = (t1 - t0) / ns

    print(
        f"{len(pathext)} file.exists checks; {len(xonsh_dir_session_cache)} paths from ∑{len(env_path)}"
    )
    print(f"🕐{dur1:.6f}\t(file.ext)\n🕐{dur2:.6f}\t(cache dirs)\t")
    assert dur2 < 0.90 * dur1  # caching dirs should be noticeable faster


import shutil

import pytest

from xonsh.pytest.tools import (
    skip_if_on_unix,
)

skip_if_no_xonsh = pytest.mark.skipif(
    shutil.which("xonsh") is None, reason="xonsh not on PATH"
)


@skip_if_no_xonsh
@skip_if_on_unix
def test_xonsh_dir_perma_cache(tmpdir, xession):
    # check that adding dirs to a XONSH_DIR_PERMA_CACHE var to cache a list of files in
    # them permanently instead of checking for the existence of every file.pathext
    # is faster
    if not ON_WINDOWS:  # other OS use this for syntax checking benefit, not speed
        return

    from os import walk

    from xonsh.procs.executables import PathCache

    xonsh_dir_perma_cache = []
    env = xession.env
    pathext = [
        ".COM",
        ".EXE",
        ".BAT",
        ".CMD",
        ".VBS",
        ".VBE",
        ".JS",
        ".JSE",
        ".WSF",
        ".WSH",
        ".MSC",
        ".PY",
        ".PYW",
        ".XSH",
    ]
    env["PATHEXT"] = pathext
    env_path = env.get("PATH", [])
    for path in env_path:  # cache all dirs in path
        f = []
        for _dirpath, _dirnames, filenames in walk(path):
            f.extend(filenames)
            break
        xonsh_dir_perma_cache += [path.rstrip(os.path.sep)]

    from math import pow
    from time import monotonic_ns as ttime

    ns = pow(10, 9)  # nanosecond, which 'monotonic_ns' are measured in

    env["XONSH_DIR_PERMA_CACHE"] = set()
    t0 = ttime()
    for _i in range(100):
        f = locate_executable("nothing", use_dir_cache_perma=False)
    t1 = ttime()
    dur1 = (t1 - t0) / ns

    env["XONSH_DIR_PERMA_CACHE"] = xonsh_dir_perma_cache
    PathCache.reset()  # previous benchmark set our singleton with an empty DIR_CACHE
    f = locate_executable("nothing", use_dir_cache_perma=True)  # to cache dirs
    t0 = ttime()
    for _i in range(100):
        f = locate_executable(
            "nothing", use_dir_cache_perma=True, path_cache_dirty=True
        )
    t1 = ttime()
    dur2 = (t1 - t0) / ns

    print(
        f"{len(pathext)} file.exists checks; {len(xonsh_dir_perma_cache)} paths from ∑{len(env_path)}"
    )
    print(f"🕐{dur1:.6f}\t(file.ext)\n🕐{dur2:.6f}\t(cache dirs)\t")
    assert dur2 < 0.90 * dur1  # caching dirs should be noticeable faster
