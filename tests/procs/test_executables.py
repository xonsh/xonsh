import os

from xonsh.environ import Env
from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import get_paths, get_possible_names, locate_executable


def test_get_possible_names():
    env = Env(PATHEXT=[".EXE", ".COM"])
    assert get_possible_names("file", env) == ["file", "file.EXE", "file.COM"]


def test_get_paths(tmpdir):
    bindir1 = str(tmpdir.mkdir("bindir1"))
    bindir2 = str(tmpdir.mkdir("bindir2"))
    env = Env(PATH=[bindir1, bindir2, bindir1, "nodir"])
    assert get_paths(env) == (bindir2, bindir1)


def test_locate_executable(tmpdir):
    bindir = tmpdir.mkdir("bindir")
    bindir.mkdir("subdir")
    executables = ["file1.EXE", "file2.COM", "file2.EXE", "file3"]
    not_executables = ["file4.EXE", "file5"]
    for exefile in executables + not_executables:
        f = bindir / exefile
        f.write_text("binary", encoding="utf8")
        if exefile in executables:
            os.chmod(f, 0o777)

    env = Env(PATH=str(bindir), PATHEXT=[".EXE", ".COM"])

    assert locate_executable("file3", env)
    assert locate_executable("file1.EXE", env)
    assert locate_executable("nofile", env) is None
    assert locate_executable("file5", env) is None
    assert locate_executable("subdir", env) is None
    if ON_WINDOWS:
        assert locate_executable("file1", env)
        assert locate_executable("file4", env)
        assert locate_executable("file2", env).endswith("file2.EXE")
    else:
        assert locate_executable("file1", env) is None
        assert locate_executable("file4", env) is None
        assert locate_executable("file2", env) is None
