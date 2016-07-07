'''Tests for xontrib.uncpushd'''

import pytest
import os
from xontrib.uncpushd import unc_pushd, unc_popd, _unc_tempDrives

import builtins
from xonsh import dirstack
from xonsh.environ import Env
from xonsh.built_ins import load_builtins
from xonsh.dirstack import DIRSTACK
from xonsh.platform import ON_WINDOWS
from xonsh.built_ins import subproc_captured_object

@pytest.fixture(scope="module")
def wd_setup(request):
    """
    test fixture creates to subdirectories under test folder containing this test file, invokes each test
    with working directory set to tests folder and DIRPATH and PWD set in builtins.__xonsh_env__
    (as is apparently needed by xonsh/dirstack.py, revealed by a close reading reveals of their unit tests.)
    """
    global _old_pwd
    global _old_env
    global _start_wd

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

    def fin():
        builtins.__xonsh_env__ = _old_env
        os.chdir(_old_pwd)

    request.addfinalizer( fin)

    load_builtins()
    _old_env = builtins.__xonsh_env__
    builtins.__xonsh_env__ = Env(CDPATH=os.path.dirname(_start_wd), PWD=_start_wd)
    os.chdir( _start_wd)

    return _start_wd

import subprocess

def do_subproc( args, msg=''):
    """Because `subproc_captured_object` fails with error `Workstation Service not started` on a `NET USE dd: \\localhost\share`..."""
    co = subprocess.run(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if co.returncode != 0:
        print('subproc returncode {}'.format(co.returncode, msg))
        print(' '.join(co.args))
        print(co.stdout)
        print(co.stderr)
        ##assert co.returncode==0, 'NET SHARE failed'
    return co.stdout, co.stderr, co.returncode

@pytest.fixture(scope="module")
def shares_setup( request):
    """create some shares to play with on current machine"""
    if ON_WINDOWS:
        shares = [ [r'uncpushd_test_cwd', 'y:', os.path.abspath( os.getcwd())]\
                 , [ r'uncpushd_test_cd1', 'w:', os.path.abspath( os.path.join(os.getcwd(), 'cdtest1'))]]
        for s,d,l in shares:      # set up some shares on local machine
            do_subproc(['net', 'share', s + '=' + l], msg='setup')
            do_subproc(['cmd', '/c', 'net', 'use', d, r"\\localhost" + '\\' + s], msg='setup')

        def fin():
            for s,d,l in shares:
                do_subproc(['net', 'use', d, '/delete'], msg='teardown:')
                do_subproc(['net', 'share', s, '/delete'], msg='teardown')

        request.addfinalizer(fin)

        return [ [ r"\\localhost" +'\\'+ s[0], s[1] , s[2]] for s in shares]

def test_unc_pushdpopd( wd_setup):
    """verify extension doesn't break unix experience if someone where so benighted as to declare these aliases not on WINDOWS
    Also validates unc_pushd/popd work for non-unc cases
    """
    unc_pushd( ['cdtest1'])
    assert os.path.abspath( os.path.join( _start_wd, 'cdtest1')) == os.getcwd()
    unc_popd([])
    assert _start_wd == os.getcwd(), "popd returned to expected dir"

def push_and_check( unc_path, drive_letter):
    o, e, c = unc_pushd( [unc_path])
    assert c == 0
    ##is dirs assert o is None
    assert e is None or len(e) == 0
    assert os.path.splitdrive( os.getcwd())[0].casefold() == drive_letter.casefold()

def test_unc_cases( wd_setup, shares_setup):
    """unc_pushd/popd handle """
    assert len(DIRSTACK) == 0
    old_drive = os.path.splitdrive(os.getcwd())[0].casefold()

    push_and_check( shares_setup[0][0], 'z:')
    push_and_check( shares_setup[0][0], 'x:')

    unc_popd([])
    assert os.path.splitdrive(os.getcwd())[0].casefold() == 'z:'

    unc_popd([])
    assert os.path.splitdrive(os.getcwd())[0].casefold() == old_drive

    pass


