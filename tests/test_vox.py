"""Vox tests"""
import io
import os
import pathlib
import stat
import subprocess as sp
import sys
import types
from typing import TYPE_CHECKING

import pytest
from py.path import local

from xonsh.platform import ON_WINDOWS
from xonsh.pytest.tools import skip_if_on_conda, skip_if_on_msys
from xontrib.voxapi import Vox, _get_vox_default_interpreter

if TYPE_CHECKING:
    from pytest_subprocess import FakeProcess

    from xontrib.vox import VoxHandler


@pytest.fixture
def venv_home(tmpdir, xession):
    """Path where VENVs are created"""
    home = tmpdir / "venvs"
    home.ensure_dir()
    # Set up an isolated venv home
    xession.env["VIRTUALENV_HOME"] = str(home)
    return home


@pytest.fixture
def venv_proc(fake_process: "FakeProcess", venv_home):
    def version_handle(process):
        ver = str(sys.version).split()[0]
        process.stdout.write(f"Python {ver}")

    def venv_handle(process):
        env_path = local(process.args[3])
        (env_path / "lib").ensure_dir()
        bin_path = env_path / ("Scripts" if ON_WINDOWS else "bin")

        (bin_path / "python").write("", ensure=True)
        (bin_path / "python.exe").write("", ensure=True)
        for file in bin_path.listdir():
            st = os.stat(str(file))
            os.chmod(str(file), st.st_mode | stat.S_IEXEC)

        for pip_name in ["pip", "pip.exe"]:
            fake_process.register(
                [str(bin_path / pip_name), "freeze", fake_process.any()], stdout=""
            )

            # will be used by `vox runin`
            fake_process.register(
                [pip_name, "--version"],
                stdout=f"pip 22.0.4 from {env_path}/lib/python3.10/site-packages/pip (python 3.10)",
            )
        fake_process.keep_last_process(True)
        return env_path

    def get_interpreters():
        interpreter = _get_vox_default_interpreter()
        yield interpreter
        if sys.executable != interpreter:
            yield sys.executable

    for cmd in get_interpreters():
        fake_process.register([cmd, "--version"], callback=version_handle)
        venv = (cmd, "-m", "venv")
        fake_process.register([*venv, fake_process.any(min=1)], callback=venv_handle)
    fake_process.keep_last_process(True)
    return fake_process


@pytest.fixture
def vox(xession, load_xontrib, venv_proc) -> "VoxHandler":
    """vox Alias function"""

    # Set up enough environment for xonsh to function
    xession.env["PWD"] = os.getcwd()
    xession.env["DIRSTACK_SIZE"] = 10
    xession.env["PATH"] = []
    xession.env["XONSH_SHOW_TRACEBACK"] = True

    load_xontrib("vox")
    vox = xession.aliases["vox"]
    return vox


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


def test_vox_flow(xession, vox, record_events, venv_home):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """

    record_events(
        "vox_on_create", "vox_on_delete", "vox_on_activate", "vox_on_deactivate"
    )

    vox(["create", "spam"])
    assert stat.S_ISDIR(venv_home.join("spam").stat().mode)
    assert record_events.last == ("vox_on_create", "spam")

    ve = vox.vox["spam"]
    assert ve.env == str(venv_home.join("spam"))
    assert os.path.isdir(ve.bin)

    assert "spam" in vox.vox
    assert "spam" in list(vox.vox)

    # activate
    vox(["activate", "spam"])
    assert xession.env["VIRTUAL_ENV"] == vox.vox["spam"].env
    assert record_events.last == ("vox_on_activate", "spam", str(ve.env))

    out = io.StringIO()
    # info
    vox(["info"], stdout=out)
    assert "spam" in out.getvalue()
    out.seek(0)

    # list
    vox(["list"], stdout=out)
    print(out.getvalue())
    assert "spam" in out.getvalue()
    out.seek(0)

    # wipe
    vox(["wipe"], stdout=out)
    print(out.getvalue())
    assert "Nothing to remove" in out.getvalue()
    out.seek(0)

    # deactivate
    vox(["deactivate"])
    assert "VIRTUAL_ENV" not in xession.env
    assert record_events.last == ("vox_on_deactivate", "spam", str(ve.env))

    # runin
    vox(["runin", "spam", "pip", "--version"], stdout=out)
    print(out.getvalue())
    assert "spam" in out.getvalue()
    out.seek(0)

    # removal
    vox(["rm", "spam", "--force"])
    assert not venv_home.join("spam").check()
    assert record_events.last == ("vox_on_delete", "spam")


def test_activate_non_vox_venv(xession, vox, record_events, venv_proc, venv_home):
    """
    Create a virtual environment using Python's built-in venv module
    (not in VIRTUALENV_HOME) and verify that vox can activate it correctly.
    """
    xession.env["PATH"] = []

    record_events("vox_on_activate", "vox_on_deactivate")

    with venv_home.as_cwd():
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
        str(pathlib.Path(str(venv_home)) / venv_dirname),
    )

    vox(["deactivate"])
    assert not env["PATH"]
    assert "VIRTUAL_ENV" not in env
    assert record_events.last == (
        "vox_on_deactivate",
        venv_dirname,
        str(pathlib.Path(str(venv_home)) / venv_dirname),
    )


@skip_if_on_msys
@skip_if_on_conda
def test_path(xession, vox, a_venv):
    """
    Test to make sure Vox properly activates and deactivates by examining $PATH
    """
    oldpath = list(xession.env["PATH"])
    vox(["activate", a_venv.basename])

    assert oldpath != xession.env["PATH"]

    vox.deactivate()

    assert oldpath == xession.env["PATH"]


def test_crud_subdir(xession, venv_home, venv_proc):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """

    vox = Vox(force_removals=True)
    vox.create("spam/eggs")
    assert stat.S_ISDIR(venv_home.join("spam", "eggs").stat().mode)

    ve = vox["spam/eggs"]
    assert ve.env == str(venv_home.join("spam", "eggs"))
    assert os.path.isdir(ve.bin)

    assert "spam/eggs" in vox
    assert "spam" not in vox

    # assert 'spam/eggs' in list(vox)  # This is NOT true on Windows
    assert "spam" not in list(vox)

    del vox["spam/eggs"]

    assert not venv_home.join("spam", "eggs").check()


def test_crud_path(xession, tmpdir, venv_proc):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    tmp = str(tmpdir)

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
def test_autovox(xession, vox, a_venv, load_xontrib, registered):
    """
    Tests that autovox works
    """
    from xonsh.dirstack import popd, pushd

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
def create_venv(venv_proc):
    vox = Vox(force_removals=True)

    def wrapped(name):
        vox.create(name)
        return local(vox[name].env)

    return wrapped


@pytest.fixture
def venvs(venv_home, create_venv):
    """Create virtualenv with names venv0, venv1"""
    from xonsh.dirstack import popd, pushd

    pushd([str(venv_home)])
    yield [create_venv(f"venv{idx}") for idx in range(2)]
    popd([])


@pytest.fixture
def a_venv(create_venv):
    return create_venv("venv0")


@pytest.fixture
def patched_cmd_cache(xession, vox, monkeypatch):
    cc = xession.commands_cache

    def no_change(self, *_):
        return False, False, False

    monkeypatch.setattr(cc, "_check_changes", types.MethodType(no_change, cc))
    monkeypatch.setattr(cc, "_update_cmds_cache", types.MethodType(no_change, cc))
    bins = {path: (path, False) for path in _PY_BINS}
    cc._cmds_cache = bins
    yield cc


_VENV_NAMES = {"venv1", "venv1/", "venv0/", "venv0"}
if ON_WINDOWS:
    _VENV_NAMES = {"venv1\\", "venv0\\", "venv0", "venv1"}

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

if ON_WINDOWS:
    _VOX_NEW_OPTS.add("--symlinks")
else:
    _VOX_NEW_OPTS.add("--copies")

_VOX_RM_OPTS = {"-f", "--force"}.union(_HELP_OPTS)


class TestVoxCompletions:
    @pytest.fixture
    def check(self, check_completer, xession, vox):
        def wrapped(cmd, positionals, options=None):
            for k in list(xession.completers):
                if k != "alias":
                    xession.completers.pop(k)
            assert check_completer(cmd) == positionals
            xession.env["ALIAS_COMPLETIONS_OPTIONS_BY_DEFAULT"] = True
            if options:
                assert check_completer(cmd) == positionals.union(options)

        return wrapped

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
                        "--prompt",
                    }
                ),
            ),
            ("vox activate", _VENV_NAMES, _HELP_OPTS.union({"-n", "--no-cd"})),
            ("vox rm", _VENV_NAMES, _VOX_RM_OPTS),
            ("vox rm venv1", _VENV_NAMES, _VOX_RM_OPTS),  # pos nargs: one or more
            ("vox rm venv1 venv2", _VENV_NAMES, _VOX_RM_OPTS),  # pos nargs: two or more
        ],
    )
    def test_vox_commands(self, args, positionals, opts, check, venvs):
        check(args, positionals, opts)

    @pytest.mark.parametrize(
        "args",
        [
            "vox new --activate --interpreter",  # option after option
            "vox new --interpreter",  # "option: first
            "vox new --activate env1 --interpreter",  # option after pos
            "vox new env1 --interpreter",  # "option: at end"
            "vox new env1 --interpreter=",  # "option: at end with
        ],
    )
    def test_interpreter(self, check, args, patched_cmd_cache):
        check(args, _PY_BINS)
