import os
import sys
import builtins

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.built_ins import run_subproc

from tools import skip_if_on_windows


@pytest.yield_fixture(autouse=True)
def chdir_to_test_dir(xonsh_builtins):
    old_cwd = os.getcwd()
    new_cwd = os.path.dirname(__file__)
    os.chdir(new_cwd)
    yield
    os.chdir(old_cwd)


@skip_if_on_windows
def test_runsubproc_simple(xonsh_builtins, xonsh_execer):
    new_cwd = os.path.dirname(__file__)
    xonsh_builtins.__xonsh_env__['PATH'] = os.path.join(new_cwd, 'bin') + \
        os.pathsep + os.path.dirname(sys.executable)
    xonsh_builtins.__xonsh_env__['XONSH_ENCODING'] = 'utf8'
    xonsh_builtins.__xonsh_env__['XONSH_ENCODING_ERRORS'] = 'surrogateescape'
    if ON_WINDOWS:
        pathext = xonsh_builtins.__xonsh_env__['PATHEXT']
        xonsh_builtins.__xonsh_env__['PATHEXT'] = ';'.join(pathext)
        pwd = 'PWD.BAT'
    else:
        pwd = 'pwd'
    out = run_subproc([[pwd]], captured='stdout')
    assert out.rstrip() == new_cwd

    
@skip_if_on_windows
def test_runsubproc_redirect_out_to_file(xonsh_builtins, xonsh_execer):
    run_subproc([['pwd', 'out>', 'tttt']], captured='stdout')
    with open('tttt') as f:
        assert f.read().rstrip() == os.getcwd()
    os.remove('tttt')

