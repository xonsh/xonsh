import os

from xonsh.environ import Env
from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import (
    get_paths,
    get_possible_names,
    locate_executable,
    locate_file,
)


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
    bindir = tmpdir.mkdir("bindir")
    bindir.mkdir("subdir")
    executables = ["file1.EXE", "file2.COM", "file2.EXE", "file3"]
    not_executables = ["file4.EXE", "file5"]
    for exefile in executables + not_executables:
        f = bindir / exefile
        f.write_text("binary", encoding="utf8")
        if exefile in executables:
            os.chmod(f, 0o777)

    pathext = [".EXE", ".COM"] if ON_WINDOWS else []
    with xession.env.swap(PATH=str(bindir), PATHEXT=pathext):
        assert locate_executable("file1.EXE")
        assert locate_executable("nofile") is None
        assert locate_executable("file5") is None
        assert locate_executable("subdir") is None
        if ON_WINDOWS:
            assert locate_executable("file1")
            assert locate_executable("file4")
            assert locate_executable("file2").endswith("file2.exe")
        else:
            assert locate_executable("file3")
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
