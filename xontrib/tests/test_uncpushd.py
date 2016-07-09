'''Tests for xontrib.uncpushd'''

import pytest
import os
from xontrib.uncpushd import unc_pushd, unc_popd, _unc_tempDrives, _do_subproc

import builtins
from xonsh.environ import Env
from xonsh.built_ins import load_builtins
from xonsh.dirstack import DIRSTACK
from xonsh.platform import ON_WINDOWS


@pytest.fixture(scope="module")
def wd_setup(request):
    """
    test fixture creates two subdirectories under test folder containing this test file, invokes each test
    with working directory set to tests folder and DIRPATH and PWD set in builtins.__xonsh_env__
    (as is apparently needed by xonsh/dirstack.py, revealed by a close reading of their unit tests.)
    """

    _old_pwd = os.getcwd()
    _start_wd = os.path.dirname(os.path.abspath(__file__))

    try:
        os.mkdir( os.path.join( _start_wd, 'cdtest1'))
    except FileExistsError:
        pass
    try:
        os.mkdir( os.path.join( _start_wd, 'cdtest2'))
    except FileExistsError:
        pass

    load_builtins()
    _old_env = builtins.__xonsh_env__
    builtins.__xonsh_env__ = Env(CDPATH=os.path.dirname(_start_wd), PWD=_start_wd)
    os.chdir( _start_wd)

    def fin():
        builtins.__xonsh_env__ = _old_env
        os.chdir(_old_pwd)

    request.addfinalizer( fin)

    return _start_wd

@pytest.fixture(scope="module")
def shares_setup( request):
    """create some shares to play with on current machine"""

    if not ON_WINDOWS:
        return []
    else:
        original_wd = os.getcwd()
        shares = [[r'uncpushd_test_cwd', 'y:', os.path.abspath(os.getcwd())] \
                  , [r'uncpushd_test_cd1', 'w:', os.path.abspath(os.path.join(os.getcwd(), 'cdtest1'))]]
        for s,d,l in shares:      # set up some shares on local machine
            _do_subproc(['net', 'share', s + '=' + l], msg='setup')
            _do_subproc(['net', 'use', d, r"\\localhost" + '\\' + s], msg='setup')

        def fin():
            # we want to delete the test shares we've created, but can't do that if unc shares in DIRSTACK
            # (left over from assert fail aborted test)
            os.chdir( original_wd)
            for dl in _unc_tempDrives:
                _do_subproc(['net', 'use', dl, '/delete'], msg='teardown1')
            for s,d,l in shares:
                _do_subproc(['net', 'use', d, '/delete'], msg='teardown2')
                _do_subproc(['net', 'share', s, '/delete'], msg='teardown')

        request.addfinalizer(fin)

        return [ [ r"\\localhost" +'\\'+ s[0], s[1] , s[2]] for s in shares]

def test_unc_pushdpopd( wd_setup):
    """verify extension doesn't break unix experience if someone where so benighted as to declare these aliases not on WINDOWS
    Also validates unc_pushd/popd work for non-unc cases
    """
    unc_pushd( ['cdtest1'])
    assert os.path.abspath( os.path.join( wd_setup, 'cdtest1')) == os.getcwd()
    unc_popd([])
    assert wd_setup == os.getcwd(), "popd returned to expected dir"

@pytest.mark.skipif( not ON_WINDOWS, reason="Windows-only UNC functionality")
def push_and_check( unc_path, drive_letter):
    o, e, c = unc_pushd( [unc_path])
    assert c == 0
    ##is dirs assert o is None
    assert e is None or len(e) == 0
    assert os.path.splitdrive( os.getcwd())[0].casefold() == drive_letter.casefold()

@pytest.mark.skipif( not ON_WINDOWS, reason="Windows-only UNC functionality")
def test_unc_cases( wd_setup, shares_setup):
    """unc_pushd/popd handle """
    assert len(DIRSTACK) == 0
    old_cwd = wd_setup

    push_and_check( shares_setup[0][0], 'z:')
    push_and_check( shares_setup[0][0], 'x:')  # 2nd pushd skips y because it was used in wd_setup.

    unc_popd([])
    assert os.path.splitdrive(os.getcwd())[0].casefold() == 'z:'

    unc_popd([])
    assert os.getcwd() == old_cwd

@pytest.mark.skipif( not ON_WINDOWS, reason="Windows-only UNC functionality")
def test_unc_repush_to_temp_driveletter( wd_setup, shares_setup):
    """verify popd doesn't unmap temp drive letter until earliest reference to drive is popped from dirstack."""

    assert len(_unc_tempDrives) == 0
    dsd = len(DIRSTACK)

    push_and_check( shares_setup[0][0], 'z:')
    assert len(_unc_tempDrives) == 1
    assert len(DIRSTACK) == dsd+1
    in_use = _do_subproc(['net', 'use']).stdout

    unc_pushd( [r'z:\cdtest1'])
    assert len(_unc_tempDrives) == 1
    assert len(DIRSTACK) == dsd + 2
    assert os.getcwd() == r'z:\cdtest1'

    unc_popd([])
    assert len(_unc_tempDrives) == 1,"should still leave one"
    assert len(DIRSTACK) == dsd + 1
    assert os.getcwd().casefold() == 'z:\\'
    assert in_use == _do_subproc(['net', 'use']).stdout

    unc_popd([])
    assert len(_unc_tempDrives) == 0
    assert len(DIRSTACK) == dsd
    assert os.getcwd().casefold() == wd_setup.casefold()

