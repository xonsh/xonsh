'''Tests for xontrib.uncpushd'''

import pytest
import os
import subprocess

from xontrib.uncpushd import unc_pushd, unc_popd, _unc_tempDrives

import builtins
from xonsh.environ import Env

from xonsh.dirstack import DIRSTACK
from xonsh.platform import ON_WINDOWS



TEST_WORK_DIR='uncpushd'

## seems like a lot of mocking needed to use xonsh functions in tests...
@pytest.yield_fixture(scope="module")
def xonsh_builtins(tmpdir_factory):
    """Mock out most of the builtins xonsh attributes."""
    temp_dir = tmpdir_factory.mktemp(TEST_WORK_DIR, numbered=False)

    builtins.__xonsh_env__ = Env(PWD=temp_dir.strpath)
    builtins.__xonsh_ctx__ = {}
    #builtins.__xonsh_shell__ = DummyShell()
    builtins.__xonsh_help__ = lambda x: x
    #builtins.__xonsh_glob__ = glob.glob
    builtins.__xonsh_exit__ = False
    builtins.__xonsh_superhelp__ = lambda x: x
    builtins.__xonsh_regexpath__ = lambda x: []
    builtins.__xonsh_expand_path__ = lambda x: x
    #builtins.__xonsh_subproc_captured__ = sp
    #builtins.__xonsh_subproc_uncaptured__ = sp
    #builtins.__xonsh_ensure_list_of_strs__ = ensure_list_of_strs
    #builtins.XonshBlockError = XonshBlockError
    #builtins.__xonsh_subproc_captured_hiddenobject__ = sp
    builtins.evalx = eval
    builtins.execx = None
    builtins.compilex = None
    builtins.aliases = {}
    yield builtins
    del builtins.__xonsh_env__
    del builtins.__xonsh_ctx__
    #del builtins.__xonsh_shell__
    del builtins.__xonsh_help__
    #del builtins.__xonsh_glob__
    del builtins.__xonsh_exit__
    del builtins.__xonsh_superhelp__
    del builtins.__xonsh_regexpath__
    del builtins.__xonsh_expand_path__
    #del builtins.__xonsh_subproc_captured__
    #del builtins.__xonsh_subproc_uncaptured__
    #del builtins.__xonsh_ensure_list_of_strs__
    #del builtins.XonshBlockError
    del builtins.evalx
    del builtins.execx
    del builtins.compilex
    del builtins.aliases

@pytest.fixture(scope="module")
def wd_setup( tmpdir_factory):
    temp_dir = tmpdir_factory.getbasetemp().join(TEST_WORK_DIR)
    os.chdir(temp_dir.strpath)

    for p in ('cdtest1', 'cdtest2'):
        try:
            os.mkdir( temp_dir.join(p).strpath)
        except FileExistsError:
            pass

    return temp_dir



@pytest.yield_fixture(scope="module")
def shares_setup( tmpdir_factory):
    """create some shares to play with on current machine.

    Yield (to test case) array of structs: [uncPath, driveLetter, equivLocalPath]
    """

    if not ON_WINDOWS:
        return []

    temp_dir = tmpdir_factory.getbasetemp().join(TEST_WORK_DIR)
    shares = [[r'uncpushd_test_cwd', 'y:', temp_dir.strpath] \
              , [r'uncpushd_test_cd1', 'w:', temp_dir.join('cdtest1').strpath]]

    for s,d,l in shares:      # set up some shares on local machine.  dirs already exist (test case must invoke wd_setup)
        subprocess.run(['net', 'share', s + '=' + l])
        subprocess.run(['net', 'use', d, r"\\localhost" + '\\' + s])

    yield [ [ r"\\localhost" +'\\'+ s[0], s[1] , s[2]] for s in shares]

    # we want to delete the test shares we've created, but can't do that if unc shares in DIRSTACK
    # (left over from assert fail aborted test)
    os.chdir( temp_dir.strpath)
    for dl in _unc_tempDrives:
        subprocess.run(['net', 'use', dl, '/delete'])
    for s,d,l in shares:
        subprocess.run(['net', 'use', d, '/delete'])
        subprocess.run(['net', 'share', s, '/delete'])


def test_unc_pushdpopd( xonsh_builtins, wd_setup):
    """verify extension doesn't break unix experience if someone where so benighted as to declare these aliases not on WINDOWS
    Also validates unc_pushd/popd work for non-unc cases
    """
    assert os.getcwd() == wd_setup
    assert wd_setup.strpath == builtins.__xonsh_env__['PWD']
    unc_pushd( ['cdtest1'])
    assert wd_setup.join('cdtest1').strpath == os.getcwd()
    unc_popd([])
    assert wd_setup == os.getcwd(), "popd returned cwd to expected dir"

@pytest.mark.skipif( not ON_WINDOWS, reason="Windows-only UNC functionality")
def push_and_check( unc_path, drive_letter):
    o, e, c = unc_pushd( [unc_path])
    assert c == 0
    ##is dirs assert o is None
    assert e is None or len(e) == 0
    assert os.path.splitdrive( os.getcwd())[0].casefold() == drive_letter.casefold()

@pytest.mark.skipif( not ON_WINDOWS, reason="Windows-only UNC functionality")
def test_unc_cases( xonsh_builtins, wd_setup, shares_setup):
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
    in_use = subprocess.run(['net', 'use']).stdout

    unc_pushd( [r'z:\cdtest1'])
    assert len(_unc_tempDrives) == 1
    assert len(DIRSTACK) == dsd + 2
    assert os.getcwd() == r'z:\cdtest1'

    unc_popd([])
    assert len(_unc_tempDrives) == 1,"should still leave one"
    assert len(DIRSTACK) == dsd + 1
    assert os.getcwd().casefold() == 'z:\\'
    assert in_use == subprocess.run(['net', 'use']).stdout

    unc_popd([])
    assert len(_unc_tempDrives) == 0
    assert len(DIRSTACK) == dsd
    assert os.getcwd().casefold() == wd_setup.strpath.casefold()

