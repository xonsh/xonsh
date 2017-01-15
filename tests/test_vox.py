"""Vox tests"""

import builtins
import stat
import os
import pytest
from xontrib.voxapi import Vox

from tools import skip_if_on_conda
from xonsh.platform import ON_WINDOWS


@skip_if_on_conda
def test_crud(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)

    last_event = None

    @xonsh_builtins.events.vox_on_create
    def create(name, **_):
        nonlocal last_event
        last_event = 'create', name

    @xonsh_builtins.events.vox_on_delete
    def delete(name, **_):
        nonlocal last_event
        last_event = 'delete', name

    vox = Vox()
    vox.create('spam')
    assert stat.S_ISDIR(tmpdir.join('spam').stat().mode)
    assert last_event == ('create', 'spam')

    ve = vox['spam']
    assert ve.env == str(tmpdir.join('spam'))
    assert os.path.isdir(ve.bin)

    assert 'spam' in vox
    assert 'spam' in list(vox)

    del vox['spam']

    assert not tmpdir.join('spam').check()
    assert last_event == ('delete', 'spam')


@skip_if_on_conda
def test_activate(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)
    # I consider the case that the user doesn't have a PATH set to be unreasonable
    xonsh_builtins.__xonsh_env__.setdefault('PATH', [])

    last_event = None

    @xonsh_builtins.events.vox_on_activate
    def activate(name, **_):
        nonlocal last_event
        last_event = 'activate', name

    @xonsh_builtins.events.vox_on_deactivate
    def deactivate(name, **_):
        nonlocal last_event
        last_event = 'deactivate', name

    vox = Vox()
    vox.create('spam')
    vox.activate('spam')
    assert xonsh_builtins.__xonsh_env__['VIRTUAL_ENV'] == vox['spam'].env
    assert last_event == ('activate', 'spam')
    vox.deactivate()
    assert 'VIRTUAL_ENV' not in xonsh_builtins.__xonsh_env__
    assert last_event == ('deactivate', 'spam')


@skip_if_on_conda
def test_path(xonsh_builtins, tmpdir):
    """
    Test to make sure Vox properly activates and deactivates by examining $PATH
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)
    # I consider the case that the user doesn't have a PATH set to be unreasonable
    xonsh_builtins.__xonsh_env__.setdefault('PATH', [])

    oldpath = list(xonsh_builtins.__xonsh_env__['PATH'])
    vox = Vox()
    vox.create('eggs')

    vox.activate('eggs')
    
    assert oldpath != xonsh_builtins.__xonsh_env__['PATH']
    
    vox.deactivate()
    
    assert oldpath == xonsh_builtins.__xonsh_env__['PATH']


@skip_if_on_conda
def test_crud_subdir(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)

    vox = Vox()
    vox.create('spam/eggs')
    assert stat.S_ISDIR(tmpdir.join('spam', 'eggs').stat().mode)

    ve = vox['spam/eggs']
    assert ve.env == str(tmpdir.join('spam', 'eggs'))
    assert os.path.isdir(ve.bin)

    assert 'spam/eggs' in vox
    assert 'spam' not in vox

    #assert 'spam/eggs' in list(vox)  # This is NOT true on Windows
    assert 'spam' not in list(vox)

    del vox['spam/eggs']

    assert not tmpdir.join('spam', 'eggs').check()

try:
    import pathlib
except ImportError:
    pass
else:
    @skip_if_on_conda
    def test_crud_path(xonsh_builtins, tmpdir):
        """
        Creates a virtual environment, gets it, enumerates it, and then deletes it.
        """
        tmp = pathlib.Path(str(tmpdir))

        vox = Vox()
        vox.create(tmp)
        assert stat.S_ISDIR(tmpdir.join('lib').stat().mode)

        ve = vox[tmp]
        assert ve.env == str(tmp)
        assert os.path.isdir(ve.bin)

        del vox[tmp]

        assert not tmpdir.check()


@skip_if_on_conda
def test_crud_subdir(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)

    vox = Vox()
    with pytest.raises(ValueError):
        if ON_WINDOWS:
            vox.create('Scripts')
        else:
            vox.create('bin')

    with pytest.raises(ValueError):
        if ON_WINDOWS:
            vox.create('spameggs/Scripts')
        else:
            vox.create('spameggs/bin')
