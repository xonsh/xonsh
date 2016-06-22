# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os
import tempfile
import builtins
from tempfile import TemporaryDirectory
from xonsh.tools import ON_WINDOWS

from xonsh.environ import (Env, format_prompt, load_static_config,
    locate_binary, partial_format_prompt)

from tools import mock_xonsh_env

def test_env_normal():
    env = Env(VAR='wakka')
    assert 'wakka' == env['VAR']

def test_env_path_list():
    env = Env(MYPATH=['/home/wakka'])
    assert ['/home/wakka'] == env['MYPATH'].paths
    env = Env(MYPATH=['wakka'])
    assert ['wakka'] == env['MYPATH'].paths

def test_env_path_str():
    env = Env(MYPATH='/home/wakka' + os.pathsep + '/home/jawaka')
    assert ['/home/wakka', '/home/jawaka'] == env['MYPATH'].paths
    env = Env(MYPATH='wakka' + os.pathsep + 'jawaka')
    assert ['wakka', 'jawaka'] == env['MYPATH'].paths

def test_env_detype():
    env = Env(MYPATH=['wakka', 'jawaka'])
    assert 'wakka' + os.pathsep + 'jawaka' == env.detype()['MYPATH']

def test_env_detype_mutable_access_clear():
    env = Env(MYPATH=['/home/wakka', '/home/jawaka'])
    assert '/home/wakka' + os.pathsep + '/home/jawaka' == env.detype()['MYPATH']
    env['MYPATH'][0] = '/home/woah'
    assert env._detyped is None
    assert '/home/woah' + os.pathsep + '/home/jawaka' == env.detype()['MYPATH']
    env = Env(MYPATH=['wakka', 'jawaka'])
    assert 'wakka' + os.pathsep + 'jawaka' == env.detype()['MYPATH']
    env['MYPATH'][0] = 'woah'
    assert env._detyped is None
    assert 'woah' + os.pathsep + 'jawaka' == env.detype()['MYPATH']

def test_env_detype_no_dict():
    env = Env(YO={'hey': 42})
    det = env.detype()
    assert 'YO' not in det

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
        assert exp == obs
    for p, exp in cases.items():
        obs = partial_format_prompt(template=p, formatter_dict=formatter_dict)
        assert exp == obs

def test_format_prompt_with_broken_template():
    for p in ('{user', '{user}{hostname'):
        assert partial_format_prompt(p) == p
        assert format_prompt(p) == p

    # '{{user' will be parsed to '{user'
    for p in ('{{user}', '{{user'):
        assert 'user' in partial_format_prompt(p)
        assert 'user' in format_prompt(p)

def test_format_prompt_with_broken_template_in_func():
    for p in (
        lambda: '{user',
        lambda: '{{user',
        lambda: '{{user}',
        lambda: '{user}{hostname',
    ):
        # '{{user' will be parsed to '{user'
        assert 'user' in partial_format_prompt(p)
        assert 'user' in format_prompt(p)

def test_format_prompt_with_invalid_func():
    def p():
        foo = bar  # raises exception
        return '{user}'
    assert isinstance(partial_format_prompt(p), str)
    assert isinstance(format_prompt(p), str)

def test_HISTCONTROL():
    env = Env(HISTCONTROL=None)
    assert isinstance(env['HISTCONTROL'], set)
    assert len(env['HISTCONTROL']) == 0

    env['HISTCONTROL'] = ''
    assert isinstance(env['HISTCONTROL'], set)
    assert len(env['HISTCONTROL']) == 0

    env['HISTCONTROL'] = 'ignoredups'
    assert isinstance(env['HISTCONTROL'], set)
    assert len(env['HISTCONTROL']) == 1
    assert ('ignoredups' in env['HISTCONTROL'])
    assert ('ignoreerr' not in env['HISTCONTROL'])

    env['HISTCONTROL'] = 'ignoreerr,ignoredups,ignoreerr'
    assert len(env['HISTCONTROL']) == 2
    assert ('ignoreerr' in env['HISTCONTROL'])
    assert ('ignoredups' in env['HISTCONTROL'])

def test_swap():
    env = Env(VAR='wakka')
    assert env['VAR'] == 'wakka'

    # positional arg
    with env.swap({'VAR': 'foo'}):
        assert env['VAR'] == 'foo'

    # make sure the environment goes back outside the context manager
    assert env['VAR'] == 'wakka'

    # kwargs only
    with env.swap(VAR1='foo', VAR2='bar'):
        assert env['VAR1'] == 'foo'
        assert env['VAR2'] == 'bar'

    # positional and kwargs
    with env.swap({'VAR3': 'baz'}, VAR1='foo', VAR2='bar'):
        assert env['VAR1'] == 'foo'
        assert env['VAR2'] == 'bar'
        assert env['VAR3'] == 'baz'

    # make sure the environment goes back outside the context manager
    assert env['VAR'] == 'wakka'
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
    assert exp == conf
    assert env['LOADED_CONFIG'] == loaded

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
                assert ( locate_binary('file1') == os.path.join(tmpdir,'file1.exe'))
                assert ( locate_binary('file1.exe') == os.path.join(tmpdir,'file1.exe'))
                assert ( locate_binary('file2') == os.path.join(tmpdir,'FILE2.BAT'))
                assert ( locate_binary('file2.bat') == os.path.join(tmpdir,'FILE2.BAT'))
                assert ( locate_binary('file3') is None)
