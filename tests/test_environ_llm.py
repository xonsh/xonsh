import os
import pathlib
from collections.abc import Iterable

from xonsh.environ import Env, EnvPath
from xonsh.tools import env_path_to_str


def test_env_path_preserves_empty_from_str():
    exp = ["a", "b", "", "c"]
    assert EnvPath(os.pathsep.join(["a", "b", "", "c"])) == exp


def test_env_path_preserves_empty_from_bytes():
    exp = ["a", "b", "", "c"]
    assert EnvPath(os.pathsep.join(["a", "b", "", "c"]).encode("utf-8")) == exp


def test_env_path_preserves_empty_from_iterable():
    class MyIterablePaths(Iterable):
        def __iter__(self):
            return iter(["a", "b", "", pathlib.Path("c")])

    assert EnvPath(MyIterablePaths()) == ["a", "b", "", "c"]


def test_env_path_preserves_leading_empty():
    # POSIX semantics: leading empty in ``MANPATH`` means "system default".
    assert EnvPath(os.pathsep.join(["", "/usr/local/man"])) == ["", "/usr/local/man"]


def test_env_path_round_trip_preserves_empty():
    # Round-trip ``str -> EnvPath -> detype`` keeps the empty entry intact,
    # so subprocesses receive the same value the user set.
    raw = os.pathsep.join(["", "/usr/local/man"])
    assert env_path_to_str(EnvPath(raw)) == raw


def test_env_preserves_empty_for_manpath():
    # ``man``/``info`` interpret an empty entry as "insert the system
    # default list here", so xonsh must not silently drop it.
    raw = os.pathsep + "/home/u/.opam/man"
    env = Env(MANPATH=raw)
    assert env["MANPATH"]._l == ["", "/home/u/.opam/man"]
    assert env.detype()["MANPATH"] == raw


def test_env_preserves_empty_for_pythonpath():
    # An empty entry in ``PYTHONPATH`` means the current directory; if we
    # drop it, ``python -c 'import m'`` stops finding modules in ``$PWD``.
    raw = os.pathsep + "/nope"
    env = Env(PYTHONPATH=raw)
    assert env["PYTHONPATH"]._l == ["", "/nope"]
    assert env.detype()["PYTHONPATH"] == raw


def test_env_windows_path_strips_empty_entries(monkeypatch):
    # ``%PATH%`` on Windows commonly ends with a trailing ``;``. That would
    # otherwise materialize as an empty ("current directory") entry, which
    # is not a documented Windows ``PATH`` semantic. Stripping happens only
    # for ``PATH``, only on Windows. The input uses plain names (no
    # drive-letter colons) so the host's ``os.pathsep`` splits the string
    # unambiguously on any platform.
    import xonsh.environ as xenviron

    monkeypatch.setattr(xenviron, "ON_WINDOWS", True)
    raw = os.pathsep.join(["a", "b", ""])
    env = Env(PATH=raw)
    assert env["PATH"]._l == ["a", "b"]


def test_env_windows_does_not_strip_other_path_vars(monkeypatch):
    # The Windows-only stripping must not bleed into other ``*PATH`` vars.
    import xonsh.environ as xenviron

    monkeypatch.setattr(xenviron, "ON_WINDOWS", True)
    raw = os.pathsep.join(["", "manuals"])
    env = Env(MANPATH=raw)
    assert env["MANPATH"]._l == ["", "manuals"]
