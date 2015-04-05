"""Tests the xonsh lexer."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true, assert_not_in

from xonsh import built_ins 
from xonsh.built_ins import Env, reglob, regexpath, helper, superhelper, \
    ensure_list_of_strs

def test_env_normal():
    env = Env(VAR='wakka')
    assert_equal('wakka', env['VAR'])

def test_env_path_list():
    env = Env(MYPATH=['wakka'])
    assert_equal(['wakka'], env['MYPATH'])

def test_env_path_str():
    env = Env(MYPATH='wakka' + os.pathsep + 'jawaka')
    assert_equal(['wakka', 'jawaka'], env['MYPATH'])

def test_env_detype():
    env = Env(MYPATH=['wakka', 'jawaka'])
    assert_equal({'MYPATH': 'wakka' + os.pathsep + 'jawaka'}, env.detype())

def test_env_detype_mutable_access_clear():
    env = Env(MYPATH=['wakka', 'jawaka'])
    assert_equal({'MYPATH': 'wakka' + os.pathsep + 'jawaka'}, env.detype())
    env['MYPATH'][0] = 'woah'
    assert_equal(None, env._detyped)
    assert_equal({'MYPATH': 'woah' + os.pathsep + 'jawaka'}, env.detype())

def test_env_detype_no_dict():
    env = Env(YO={'hey': 42})
    det = env.detype()
    assert_not_in('YO', det)

def test_reglob_tests():
    testfiles = reglob('test_.*')
    for f in testfiles:
        assert_true(f.startswith('test_'))

def test_repath_home_itself():
    exp = os.path.expanduser('~')
    obs = regexpath('~')
    assert_equal(1, len(obs))
    assert_equal(exp, obs[0])

def test_repath_home_contents():
    home = os.path.expanduser('~')
    exp = os.listdir(home)
    exp = {os.path.join(home, p) for p in exp}
    obs = set(regexpath('~/.*'))
    assert_equal(exp, obs)

def test_repath_home_var():
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    obs = regexpath('$HOME')
    assert_equal(1, len(os.environ))
    built_ins.ENV.undo_replace_env()
    assert_equal(1, len(obs))
    assert_equal(exp, obs[0])

def test_repath_home_var_brace():
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    obs = regexpath('${HOME}')
    assert_equal(1, len(os.environ))
    built_ins.ENV.undo_replace_env()
    assert_equal(1, len(obs))
    assert_equal(exp, obs[0])

def test_helper_int():
    helper(int, 'int')

def test_helper_helper():
    helper(helper, 'helper')

def test_helper_env():
    helper(Env, 'Env')

def test_superhelper_int():
    superhelper(int, 'int')

def test_superhelper_helper():
    superhelper(helper, 'helper')

def test_superhelper_env():
    superhelper(Env, 'Env')

def test_ensure_list_of_strs():
    cases = [(['yo'], 'yo'), (['yo'], ['yo']), (['42'], 42), (['42'], [42])]
    for exp, inp in cases:
        obs = ensure_list_of_strs(inp)
        yield assert_equal, exp, obs


if __name__ == '__main__':
    nose.runmodule()
