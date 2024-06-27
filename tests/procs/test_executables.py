import os

from xonsh.environ import Env
from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import get_possible_names, locate_executable


def test_get_possible_names(xession):
    env = Env(PATHEXT=[".EXE", ".COM"])
    assert get_possible_names("file", env) == ["file", "file.EXE", "file.COM"]


def test_xonshrc(tmpdir, xession):
    bindir = tmpdir.mkdir("bindir")
    bindir.mkdir("subdir")
    executables = ["cmd.EXE", "cmdcom.COM", "cmdcom.EXE", "runme"]
    not_executables = ["no.EXE", "nonono"]
    for exefile in executables + not_executables:
        f = bindir / exefile
        f.write_text("binary", encoding="utf8")
        if exefile in executables:
            os.chmod(f, 0o777)

    env = Env(PATH=str(bindir), PATHEXT=[".EXE", ".COM"])

    assert locate_executable("runme", env)
    assert locate_executable("cmd.EXE", env)
    assert locate_executable("nofile", env) is None
    assert locate_executable("nonono", env) is None
    assert locate_executable("subdir", env) is None
    if ON_WINDOWS:
        assert locate_executable("cmd", env)
        assert locate_executable("no", env)
        assert locate_executable("cmdcom", env).endswith("cmdcom.EXE")
    else:
        assert locate_executable("cmd", env) is None
        assert locate_executable("no", env) is None
        assert locate_executable("cmdcom", env) is None
