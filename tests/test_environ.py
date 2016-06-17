# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os
import tempfile
import builtins
from tempfile import TemporaryDirectory
from xonsh.tools import ON_WINDOWS


import nose
from nose.tools import (assert_equal, assert_true, assert_not_in,
    assert_is_instance, assert_in, assert_raises)

from xonsh.environ import (Env, format_prompt, load_static_config,
    locate_binary, partial_format_prompt)

from tools import mock_xonsh_env

def test_env_normal():
    env = Env(VAR='wakka')
    assert_equal('wakka', env['VAR'])

def test_env_path_list():
    env = Env(MYPATH=['/home/wakka'])
    assert_equal(['/home/wakka'], env['MYPATH'].paths)
    env = Env(MYPATH=['wakka'])
    assert_equal([os.path.abspath('wakka')], env['MYPATH'].paths)

def test_env_path_str():
    env = Env(MYPATH='/home/wakka' + os.pathsep + '/home/jawaka')
    assert_equal(['/home/wakka', '/home/jawaka'], env['MYPATH'].paths)
    env = Env(MYPATH='wakka' + os.pathsep + 'jawaka')
    assert_equal([os.path.abspath('wakka'), os.path.abspath('jawaka')],
                 env['MYPATH'].paths)

def test_env_detype():
    env = Env(MYPATH=['wakka', 'jawaka'])
    assert_equal(os.path.abspath('wakka') + os.pathsep + \
                 os.path.abspath('jawaka'),
                 env.detype()['MYPATH'])

def test_env_detype_mutable_access_clear():
    env = Env(MYPATH=['/home/wakka', '/home/jawaka'])
    assert_equal('/home/wakka' + os.pathsep + '/home/jawaka',
                 env.detype()['MYPATH'])
    env['MYPATH'][0] = '/home/woah'
    assert_equal(None, env._detyped)
    assert_equal('/home/woah' + os.pathsep + '/home/jawaka',
                 env.detype()['MYPATH'])

    env = Env(MYPATH=['wakka', 'jawaka'])
    assert_equal(os.path.abspath('wakka') + os.pathsep + \
                 os.path.abspath('jawaka'),
                 env.detype()['MYPATH'])
    env['MYPATH'][0] = 'woah'
    assert_equal(None, env._detyped)
    assert_equal(os.path.abspath('woah') + os.pathsep + \
                 os.path.abspath('jawaka'),
                 env.detype()['MYPATH'])

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
    for p, exp in cases.items():
        obs = partial_format_prompt(template=p, formatter_dict=formatter_dict)
        yield assert_equal, exp, obs

def test_format_prompt_with_broken_template():
    for p in ('{user', '{user}{hostname'):
        assert_equal(partial_format_prompt(p), p)
        assert_equal(format_prompt(p), p)

    # '{{user' will be parsed to '{user'
    for p in ('{{user}', '{{user'):
        assert_in('user', partial_format_prompt(p))
        assert_in('user', format_prompt(p))

def test_format_prompt_with_broken_template_in_func():
    for p in (
        lambda: '{user',
        lambda: '{{user',
        lambda: '{{user}',
        lambda: '{user}{hostname',
    ):
        # '{{user' will be parsed to '{user'
        assert_in('user', partial_format_prompt(p))
        assert_in('user', format_prompt(p))

def test_format_prompt_with_invalid_func():
    def p():
        foo = bar  # raises exception
        return '{user}'
    assert_is_instance(partial_format_prompt(p), str)
    assert_is_instance(format_prompt(p), str)

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
    env = Env({'XONSH_SHOW_TRACEBACK': False})
    f = tempfile.NamedTemporaryFile(delete=False)
    with mock_xonsh_env(env):
        f.write(s)
        f.close()
        conf = load_static_config(env, f.name)
    os.unlink(f.name)
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

if ON_WINDOWS:
    def test_locate_binary_on_windows():
        files = ('file1.exe', 'FILE2.BAT', 'file3.txt')
        with TemporaryDirectory() as tmpdir:
            for fname in files:
                fpath = os.path.join(tmpdir, fname)
                with open(fpath, 'w') as f:
                    f.write(fpath)
            env = Env({'PATH': [tmpdir], 'PATHEXT': ['.COM', '.EXE', '.BAT']})
            with mock_xonsh_env(env):
                assert_equal( locate_binary('file1'), os.path.join(tmpdir,'file1.exe'))
                assert_equal( locate_binary('file1.exe'), os.path.join(tmpdir,'file1.exe'))
                assert_equal( locate_binary('file2'), os.path.join(tmpdir,'FILE2.BAT'))
                assert_equal( locate_binary('file2.bat'), os.path.join(tmpdir,'FILE2.BAT'))
                assert_equal( locate_binary('file3'), None)



if __name__ == '__main__':
    nose.runmodule()
