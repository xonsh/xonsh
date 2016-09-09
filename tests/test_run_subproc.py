import os
import sys

import pytest

from xonsh.built_ins import run_subproc



@pytest.yield_fixture(autouse=True, scope='module')
def chdir_to_test_dir():
    old_cwd = os.getcwd()
    new_cwd = os.path.dirname(__file__)
    os.chdir(new_cwd)
    yield
    os.chdir(old_cwd)

#def test_runsubproc_simple(capfd, xonsh_builtins, xonsh_execer):
def test_runsubproc_simple(xonsh_builtins, xonsh_execer):
    new_cwd = os.path.dirname(__file__)
    xonsh_builtins.__xonsh_env__['PATH'] = os.path.join(new_cwd, 'bin') + \
        os.pathsep + os.path.dirname(sys.executable)
    out = run_subproc([['pwd']], captured='stdout')
    #run_subproc([['pwd']])
    #out, err = capfd.readouterr()
    assert out.rstrip() == new_cwd

def test_runsubproc_pipe(capfd, xonsh_builtins, xonsh_execer):
    run_subproc([['ls'], '|', ['grep', '-i', 'sample']])
    out, err = capfd.readouterr()
    assert out.rstrip() == 'sample.xsh'


def test_runsubproc_redirect_out_to_file(xonsh_builtins, xonsh_execer):
    run_subproc([['pwd', 'out>', 'tttt']])
    with open('tttt') as f:
        assert f.read().rstrip() == os.getcwd()
    os.remove('tttt')

