"""Vox tests"""

import builtins
import stat
import os
from xontrib.voxapi import Vox

def test_crud(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)
    vox = Vox()
    vox.create('spam')
    assert stat.S_ISDIR(tmpdir.join('spam').stat().mode)

    env, bin = vox['spam']
    assert env == str(tmpdir.join('spam'))
    assert os.path.isdir(bin)

    assert 'spam' in vox

    del vox['spam']

    assert not tmpdir.join('spam').check()

def test_activate(xonsh_builtins, tmpdir):
    """
    Creates a virtual environment, gets it, enumerates it, and then deletes it.
    """
    xonsh_builtins.__xonsh_env__['VIRTUALENV_HOME'] = str(tmpdir)
    # I consider the case that the user doesn't have a PATH set to be unreasonable
    xonsh_builtins.__xonsh_env__.setdefault('PATH', [])
    vox = Vox()
    vox.create('spam')
    vox.activate('spam')
    assert xonsh_builtins.__xonsh_env__['VIRTUAL_ENV'] == vox['spam'].env
    vox.deactivate()
    assert 'VIRTUAL_ENV' not in xonsh_builtins.__xonsh_env__
