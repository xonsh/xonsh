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
