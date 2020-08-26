"""Vox tests"""

import stat
import os
import subprocess as sp
import pytest
import sys
from xontrib.voxapi import Vox

from tools import skip_if_on_conda, skip_if_on_msys
from xonsh.platform import ON_WINDOWS


@skip_if_on_msys
@skip_if_on_conda
def test_crud(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)

    last_event = None

    @xonsh_builtins.events.vox_on_create
    def create(name, **_):
        nonlocal last_event
        last_event = "create", name

    @xonsh_builtins.events.vox_on_delete
    def delete(name, **_):
        nonlocal last_event
        last_event = "delete", name

    vox = Vox()
    vox.create("spam")
    assert stat.S_ISDIR(tmpdir.join("spam").stat().mode)
    assert last_event == ("create", "spam")

    ve = vox["spam"]
    assert ve.env == str(tmpdir.join("spam"))
    assert os.path.isdir(ve.bin)

    assert "spam" in vox
    assert "spam" in list(vox)

    del vox["spam"]

    assert not tmpdir.join("spam").check()
    assert last_event == ("delete", "spam")


@skip_if_on_msys
@skip_if_on_conda
def test_activate(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)
    # I consider the case that the user doesn't have a PATH set to be unreasonable
    xonsh_builtins.__xonsh__.env.setdefault("PATH", [])

    last_event = None

    @xonsh_builtins.events.vox_on_activate
    def activate(name, **_):
        nonlocal last_event
        last_event = "activate", name

    @xonsh_builtins.events.vox_on_deactivate
    def deactivate(name, **_):
        nonlocal last_event
        last_event = "deactivate", name

    vox = Vox()
    vox.create("spam")
    vox.activate("spam")
    assert xonsh_builtins.__xonsh__.env["VIRTUAL_ENV"] == vox["spam"].env
    assert last_event == ("activate", "spam")
    vox.deactivate()
    assert "VIRTUAL_ENV" not in xonsh_builtins.__xonsh__.env
    assert last_event == ("deactivate", "spam")


@skip_if_on_msys
@skip_if_on_conda
def test_activate_non_vox_venv(xonsh_builtins, tmpdir):
    """
    Create a virtual environment using Python's built-in venv module
    (not in VIRTUALENV_HOME) and verify that vox can activate it correctly.
    """
    xonsh_builtins.__xonsh__.env.setdefault("PATH", [])

    last_event = None

    @xonsh_builtins.events.vox_on_activate
    def activate(name, path, **_):
        nonlocal last_event
        last_event = "activate", name, path

    @xonsh_builtins.events.vox_on_deactivate
    def deactivate(name, path, **_):
        nonlocal last_event
        last_event = "deactivate", name, path

    with tmpdir.as_cwd():
        venv_dirname = "venv"
        sp.run([sys.executable, "-m", "venv", venv_dirname])
        vox = Vox()
        vox.activate(venv_dirname)
        vxv = vox[venv_dirname]

    env = xonsh_builtins.__xonsh__.env
    assert os.path.isabs(vxv.bin)
    assert env["PATH"][0] == vxv.bin
    assert os.path.isabs(vxv.env)
    assert env["VIRTUAL_ENV"] == vxv.env
    assert last_event == (
        "activate",
        venv_dirname,
        str(pathlib.Path(str(tmpdir)) / "venv"),
    )

    vox.deactivate()
    assert not env["PATH"]
    assert "VIRTUAL_ENV" not in env
    assert last_event == (
        "deactivate",
        tmpdir.join(venv_dirname),
        str(pathlib.Path(str(tmpdir)) / "venv"),
    )


@skip_if_on_msys
@skip_if_on_conda
def test_path(xonsh_builtins, tmpdir):
    """
    Test to make sure Vox properly activates and deactivates by examining $PATH
    """
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)
    # I consider the case that the user doesn't have a PATH set to be unreasonable
    xonsh_builtins.__xonsh__.env.setdefault("PATH", [])

    oldpath = list(xonsh_builtins.__xonsh__.env["PATH"])
    vox = Vox()
    vox.create("eggs")

    vox.activate("eggs")

    assert oldpath != xonsh_builtins.__xonsh__.env["PATH"]

    vox.deactivate()

    assert oldpath == xonsh_builtins.__xonsh__.env["PATH"]


@skip_if_on_msys
@skip_if_on_conda
def test_crud_subdir(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)

    vox = Vox()
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


try:
    import pathlib
except ImportError:
    pass
else:

    @skip_if_on_msys
    @skip_if_on_conda
    def test_crud_path(xonsh_builtins, tmpdir):
        """
        Creates a virtual environment, gets it, enumerates it, and then deletes it.
        """
        tmp = pathlib.Path(str(tmpdir))

        vox = Vox()
        vox.create(tmp)
        assert stat.S_ISDIR(tmpdir.join("lib").stat().mode)

        ve = vox[tmp]
        assert ve.env == str(tmp)
        assert os.path.isdir(ve.bin)

        del vox[tmp]

        assert not tmpdir.check()


@skip_if_on_msys
@skip_if_on_conda
def test_reserved_names(xonsh_builtins, tmpdir):
    """
    Tests that reserved words are disallowed.
    """
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)

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


@skip_if_on_msys
@skip_if_on_conda
def test_autovox(xonsh_builtins, tmpdir):
    """
    Tests that autovox works
    """
    import importlib
    import xonsh.dirstack

    # Set up an isolated venv home
    xonsh_builtins.__xonsh__.env["VIRTUALENV_HOME"] = str(tmpdir)

    # Makes sure that event handlers are registered
    import xontrib.autovox

    importlib.reload(xontrib.autovox)

    # Set up enough environment for xonsh to function
    xonsh_builtins.__xonsh__.env["PWD"] = os.getcwd()
    xonsh_builtins.__xonsh__.env["DIRSTACK_SIZE"] = 10
    xonsh_builtins.__xonsh__.env["PATH"] = []

    xonsh_builtins.__xonsh__.env["XONSH_SHOW_TRACEBACK"] = True

    @xonsh_builtins.events.autovox_policy
    def policy(path, **_):
        print("Checking", repr(path), vox.active())
        if str(path) == str(tmpdir):
            return "myenv"

    vox = Vox()

    print(xonsh_builtins.__xonsh__.env["PWD"])
    xonsh.dirstack.pushd([str(tmpdir)])
    print(xonsh_builtins.__xonsh__.env["PWD"])
    assert vox.active() is None
    xonsh.dirstack.popd([])
    print(xonsh_builtins.__xonsh__.env["PWD"])

    vox.create("myenv")
    xonsh.dirstack.pushd([str(tmpdir)])
    print(xonsh_builtins.__xonsh__.env["PWD"])
    assert vox.active() == "myenv"
    xonsh.dirstack.popd([])
    print(xonsh_builtins.__xonsh__.env["PWD"])
