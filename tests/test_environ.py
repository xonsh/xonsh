# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os
import tempfile
import builtins

import nose
from nose.tools import (assert_equal, assert_true, assert_not_in,
    assert_is_instance, assert_in, assert_raises)

from xonsh.environ import Env, format_prompt, load_static_config

from tests.tools import mock_xonsh_env

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

def test_swap():
    env = Env(VAR='wakka')
    assert_equal(env['VAR'], 'wakka')

    # positional arg
    with env.swap({'VAR': 'foo'}):
        assert_equal(env['VAR'], 'foo')

    # make sure the environment goes back outside the context manager
    assert_equal(env['VAR'], 'wakka')

    # kwargs only
    with env.swap(VAR1='foo', VAR2='bar'):
        assert_equal(env['VAR1'], 'foo')
        assert_equal(env['VAR2'], 'bar')

    # positional and kwargs
    with env.swap({'VAR3': 'baz'}, VAR1='foo', VAR2='bar'):
        assert_equal(env['VAR1'], 'foo')
        assert_equal(env['VAR2'], 'bar')
        assert_equal(env['VAR3'], 'baz')

    # make sure the environment goes back outside the context manager
    assert_equal(env['VAR'], 'wakka')
    assert 'VAR1' not in env
    assert 'VAR2' not in env
    assert 'VAR3' not in env

def check_load_static_config(s, exp, loaded):
    env = {'XONSH_SHOW_TRACEBACK': False}
    with tempfile.NamedTemporaryFile() as f, mock_xonsh_env(env):
        f.write(s)
        f.flush()
        conf = load_static_config(env, f.name)
    assert_equal(exp, conf)
    assert_equal(env['LOADED_CONFIG'], loaded)

def test_load_static_config_works():
    s = b'{"best": "awash"}'
    check_load_static_config(s, {'best': 'awash'}, True)

def test_load_static_config_type_fail():
    s = b'["best", "awash"]'
    check_load_static_config(s, {}, False)

def test_load_static_config_json_fail():
    s = b'{"best": "awash"'
    check_load_static_config(s, {}, False)


if __name__ == '__main__':
    nose.runmodule()
