"""Vox tests"""
import pathlib
import stat
import os
import subprocess as sp
import types

import pytest
import sys
from xontrib.voxapi import Vox

from tools import skip_if_on_conda, skip_if_on_msys
from xonsh.platform import ON_WINDOWS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xontrib.vox import VoxHandler


@pytest.fixture
def vox(xession, tmpdir, load_xontrib) -> "VoxHandler":
    """vox Alias function"""

    # Set up an isolated venv home
    xession.env["VIRTUALENV_HOME"] = str(tmpdir)

    # Set up enough environment for xonsh to function
    xession.env["PWD"] = os.getcwd()
    xession.env["DIRSTACK_SIZE"] = 10
    xession.env["PATH"] = []
    xession.env["XONSH_SHOW_TRACEBACK"] = True

    load_xontrib("vox")

    yield xession.aliases["vox"]


@pytest.fixture
def record_events(xession):
    class Listener:
        def __init__(self):
            self.last = None

        def listener(self, name):
            def _wrapper(**kwargs):
                self.last = (name,) + tuple(kwargs.values())

            return _wrapper

        def __call__(self, *events: str):
            for name in events:
                event = getattr(xession.builtins.events, name)
                event(self.listener(name))

    yield Listener()


@skip_if_on_msys
@skip_if_on_conda
def test_vox_flow(xession, vox, record_events, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xession.env["VIRTUALENV_HOME"] = str(tmpdir)

    record_events(
        "vox_on_create", "vox_on_delete", "vox_on_activate", "vox_on_deactivate"
    )

    vox(["create", "spam"])
    assert stat.S_ISDIR(tmpdir.join("spam").stat().mode)
    assert record_events.last == ("vox_on_create", "spam")

    ve = vox.vox["spam"]
    assert ve.env == str(tmpdir.join("spam"))
    assert os.path.isdir(ve.bin)

    assert "spam" in vox.vox
    assert "spam" in list(vox.vox)

    # activate/deactivate
    vox(["activate", "spam"])
    assert xession.env["VIRTUAL_ENV"] == vox.vox["spam"].env
    assert record_events.last == ("vox_on_activate", "spam", str(ve.env))
    vox.deactivate()
    assert "VIRTUAL_ENV" not in xession.env
    assert record_events.last == ("vox_on_deactivate", "spam", str(ve.env))

    # removal
    vox(["rm", "spam", "--force"])
    assert not tmpdir.join("spam").check()
    assert record_events.last == ("vox_on_delete", "spam")


@skip_if_on_msys
@skip_if_on_conda
def test_activate_non_vox_venv(xession, vox, record_events, tmpdir):
    """
    Create a virtual environment using Python's built-in venv module
    (not in VIRTUALENV_HOME) and verify that vox can activate it correctly.
    """
    xession.env["PATH"] = []

    record_events("vox_on_activate", "vox_on_deactivate")

    with tmpdir.as_cwd():
        venv_dirname = "venv"
        sp.run([sys.executable, "-m", "venv", venv_dirname])
        vox(["activate", venv_dirname])
        vxv = vox.vox[venv_dirname]

    env = xession.env
    assert os.path.isabs(vxv.bin)
    assert env["PATH"][0] == vxv.bin
    assert os.path.isabs(vxv.env)
    assert env["VIRTUAL_ENV"] == vxv.env
    assert record_events.last == (
        "vox_on_activate",
        venv_dirname,
        str(pathlib.Path(str(tmpdir)) / venv_dirname),
    )

    vox(["deactivate"])
    assert not env["PATH"]
    assert "VIRTUAL_ENV" not in env
    assert record_events.last == (
        "vox_on_deactivate",
        venv_dirname,
        str(pathlib.Path(str(tmpdir)) / venv_dirname),
    )


@skip_if_on_msys
@skip_if_on_conda
def test_path(xession, vox, tmpdir, a_venv):
    """
    Test to make sure Vox properly activates and deactivates by examining $PATH
    """
    oldpath = list(xession.env["PATH"])
    vox(["activate", a_venv.basename])

    assert oldpath != xession.env["PATH"]

    vox.deactivate()

    assert oldpath == xession.env["PATH"]


@skip_if_on_msys
@skip_if_on_conda
def test_crud_subdir(xession, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xession.env["VIRTUALENV_HOME"] = str(tmpdir)

    vox = Vox(force_removals=True)
    vox.create("spam/eggs")
    assert stat.S_ISDIR(tmpdir.join("spam", "eggs").stat().mode)

    ve = vox["spam/eggs"]
    assert ve.env == str(tmpdir.join("spam", "eggs"))
    assert os.path.isdir(ve.bin)

    assert "spam/eggs" in vox
    assert "spam" not in vox

    # assert 'spam/eggs' in list(vox)  # This is NOT true on Windows
    assert "spam" not in list(vox)

    del vox["spam/eggs"]

    assert not tmpdir.join("spam", "eggs").check()


@skip_if_on_msys
@skip_if_on_conda
def test_crud_path(xession, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    tmp = pathlib.Path(str(tmpdir))

    vox = Vox(force_removals=True)
    vox.create(tmp)
    assert stat.S_ISDIR(tmpdir.join("lib").stat().mode)

    ve = vox[tmp]
    assert ve.env == str(tmp)
    assert os.path.isdir(ve.bin)

    del vox[tmp]

    assert not tmpdir.check()


@skip_if_on_msys
@skip_if_on_conda
def test_reserved_names(xession, tmpdir):
    """
    Tests that reserved words are disallowed.
    """
    xession.env["VIRTUALENV_HOME"] = str(tmpdir)

    vox = Vox()
    with pytest.raises(ValueError):
        if ON_WINDOWS:
            vox.create("Scripts")
        else:
            vox.create("bin")

    with pytest.raises(ValueError):
        if ON_WINDOWS:
            vox.create("spameggs/Scripts")
        else:
            vox.create("spameggs/bin")


@pytest.mark.parametrize("registered", [False, True])
@skip_if_on_msys
@skip_if_on_conda
def test_autovox(xession, tmpdir, vox, a_venv, load_xontrib, registered):
    """
    Tests that autovox works
    """
    from xonsh.dirstack import pushd, popd

    # Makes sure that event handlers are registered
    load_xontrib("autovox")

    env_name = a_venv.basename
    env_path = str(a_venv)

    # init properly
    assert vox.parser

    def policy(path, **_):
        if str(path) == env_path:
            return env_name

    if registered:
        xession.builtins.events.autovox_policy(policy)

    pushd([env_path])
    value = env_name if registered else None
    assert vox.vox.active() == value
    popd([])


@pytest.fixture
def venv_home(tmpdir):
    """Path where VENVs are created"""
    return tmpdir


@pytest.fixture
def venvs(venv_home):
    """Create virtualenv with names venv0, venv1"""
    from xonsh.dirstack import pushd, popd

    pushd([str(venv_home)])
    paths = []
    for idx in range(2):
        env_path = venv_home / f"venv{idx}"
        bin_path = env_path / "bin"
        paths.append(env_path)

        (bin_path / "python").write("", ensure=True)
        (bin_path / "python.exe").write("", ensure=True)
        for file in bin_path.listdir():
            st = os.stat(str(file))
            os.chmod(str(file), st.st_mode | stat.S_IEXEC)
    yield paths
    popd([])


@pytest.fixture
def a_venv(venvs):
    return venvs[0]


@pytest.fixture
def patched_cmd_cache(xession, vox, venvs, monkeypatch):
    cc = xession.commands_cache

    def no_change(self, *_):
        return False, False, False

    monkeypatch.setattr(cc, "_check_changes", types.MethodType(no_change, cc))
    monkeypatch.setattr(cc, "_update_cmds_cache", types.MethodType(no_change, cc))
    monkeypatch.setattr(cc, "cache_file", None)
    bins = {path: (path, False) for path in _PY_BINS}
    cc._cmds_cache.update(bins)
    yield cc


_VENV_NAMES = {"venv1", "venv1/", "venv0/", "venv0"}
if ON_WINDOWS:
    _VENV_NAMES = {"venv1\\", "venv0\\"}

_HELP_OPTS = {
    "-h",
    "--help",
}
_PY_BINS = {"/bin/python2", "/bin/python3"}

_VOX_NEW_OPTS = {
    "--ssp",
    "--system-site-packages",
    "--without-pip",
}.union(_HELP_OPTS)
_VOX_NEW_EXP = _PY_BINS.union(_VOX_NEW_OPTS)

if ON_WINDOWS:
    _VOX_NEW_OPTS.add("--symlinks")
else:
    _VOX_NEW_OPTS.add("--copies")

_VOX_RM_OPTS = {"-f", "--force"}.union(_HELP_OPTS)


@pytest.mark.parametrize(
    "args, positionals, opts",
    [
        (
            "vox",
            {
                "delete",
                "new",
                "remove",
                "del",
                "workon",
                "list",
                "exit",
                "info",
                "ls",
                "rm",
                "deactivate",
                "activate",
                "enter",
                "create",
                "project-get",
                "project-set",
                "runin",
                "runin-all",
                "toggle-ssp",
                "wipe",
                "upgrade",
            },
            _HELP_OPTS,
        ),
        (
            "vox create",
            set(),
            _VOX_NEW_OPTS.union(
                {
                    "-a",
                    "--activate",
                    "--wp",
                    "--without-pip",
                    "-p",
                    "--interpreter",
                    "-i",
                    "--install",
                    "-l",
                    "--link",
                    "--link-project",
                    "-r",
                    "--requirements",
                    "-t",
                    "--temp",
                }
            ),
        ),
        ("vox activate", _VENV_NAMES, _HELP_OPTS.union({"-n", "--no-cd"})),
        ("vox rm", _VENV_NAMES, _VOX_RM_OPTS),
        ("vox rm venv1", _VENV_NAMES, _VOX_RM_OPTS),  # pos nargs: one or more
        ("vox rm venv1 venv2", _VENV_NAMES, _VOX_RM_OPTS),  # pos nargs: two or more
        ("vox new --activate --interpreter", _PY_BINS, set()),  # option after option
        ("vox new --interpreter", _PY_BINS, set()),  # "option: first
        ("vox new --activate env1 --interpreter", _PY_BINS, set()),  # option after pos
        ("vox new env1 --interpreter", _PY_BINS, set()),  # "option: at end"
        ("vox new env1 --interpreter=", _PY_BINS, set()),  # "option: at end with
    ],
)
def test_vox_completer(
    args, check_completer, positionals, opts, xession, patched_cmd_cache, venv_home
):
    xession.env["XONSH_DATA_DIR"] = venv_home
    if positionals:
        assert check_completer(args) == positionals
    xession.env["ALIAS_COMPLETIONS_OPTIONS_BY_DEFAULT"] = True
    if opts:
        assert check_completer(args) == positionals.union(opts)
