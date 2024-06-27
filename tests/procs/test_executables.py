import os

from xonsh.platform import ON_WINDOWS
from xonsh.procs.executables import get_possible_names, locate_executable


def test_get_possible_names(xession):
    xession.env["PATHEXT"] = [".EXE", ".COM"]
    assert get_possible_names("file") == ["file", "file.EXE", "file.COM"]


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

    xession.env["PATH"].append(bindir)
    xession.env["PATHEXT"] = [".EXE", ".COM"]

    assert locate_executable("runme")
    assert locate_executable("cmd")
    assert locate_executable("cmd.EXE")
    assert locate_executable("cmdcom").endswith("cmdcom.EXE")
    assert locate_executable("nofile") is None
    assert locate_executable("nonono") is None
    assert locate_executable("subdir") is None
    if ON_WINDOWS:
        assert locate_executable("no")
    else:
        assert locate_executable("no") is None
