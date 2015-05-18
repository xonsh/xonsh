"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true, assert_not_in

from xonsh.environ import Env

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


if __name__ == '__main__':
    nose.runmodule()
