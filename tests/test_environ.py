# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import (assert_equal, assert_true, assert_not_in,
                        assert_is_instance, assert_in)

from xonsh.environ import Env, format_prompt

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

def test_format_prompt():
    formatter_dict = {
        'a_string': 'cat',
        'none': (lambda: None),
        'f': (lambda: 'wakka'),
        }
    cases = {
        'my {a_string}': 'my cat',
        'my {none}{a_string}': 'my cat',
        '{f} jawaka': 'wakka jawaka',
        }
    for p, exp in cases.items():
        obs = format_prompt(template=p, formatter_dict=formatter_dict)
        yield assert_equal, exp, obs

def test_HISTCONTROL():
    env = Env(HISTCONTROL=None)
    assert_is_instance(env['HISTCONTROL'], set)
    assert_equal(len(env['HISTCONTROL']), 0)

    env['HISTCONTROL'] = ''
    assert_is_instance(env['HISTCONTROL'], set)
    assert_equal(len(env['HISTCONTROL']), 0)

    env['HISTCONTROL'] = 'ignoredups'
    assert_is_instance(env['HISTCONTROL'], set)
    assert_equal(len(env['HISTCONTROL']), 1)
    assert_true('ignoredups' in env['HISTCONTROL'])
    assert_true('ignoreerr' not in env['HISTCONTROL'])

    env['HISTCONTROL'] = 'ignoreerr,ignoredups,ignoreerr'
    assert_equal(len(env['HISTCONTROL']), 2)
    assert_true('ignoreerr' in env['HISTCONTROL'])
    assert_true('ignoredups' in env['HISTCONTROL'])

if __name__ == '__main__':
    nose.runmodule()
