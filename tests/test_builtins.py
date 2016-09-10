# -*- coding: utf-8 -*-
"""Tests the xonsh builtins."""
from __future__ import unicode_literals, print_function
import os
import re
import builtins
import types
from ast import AST

import pytest

from xonsh import built_ins
from xonsh.built_ins import reglob, pathsearch, helper, superhelper, \
    ensure_list_of_strs, list_of_strs_or_callables, regexsearch, \
    globsearch, expand_path, convert_macro_arg, in_macro_call, call_macro, \
    enter_macro
from xonsh.environ import Env

from tools import skip_if_on_windows


HOME_PATH = os.path.expanduser('~')


@pytest.fixture(autouse=True)
def xonsh_execer_autouse(xonsh_execer):
    return xonsh_execer

@pytest.mark.parametrize('testfile', reglob('test_.*'))
def test_reglob_tests(testfile):
    assert (testfile.startswith('test_'))


@pytest.fixture
def home_env(xonsh_builtins):
    """Set `__xonsh_env__ ` to a new Env instance on `xonsh_builtins`"""
    xonsh_builtins.__xonsh_env__ = Env(HOME=HOME_PATH)
    return xonsh_builtins


@skip_if_on_windows
def test_repath_backslash(home_env):
    exp = os.listdir(HOME_PATH)
    exp = {p for p in exp if re.match(r'\w\w.*', p)}
    exp = {os.path.join(HOME_PATH, p) for p in exp}
    obs = set(pathsearch(regexsearch, r'~/\w\w.*'))
    assert exp ==  obs


@skip_if_on_windows
def test_repath_HOME_PATH_itself(home_env):
    exp = HOME_PATH
    obs = pathsearch(regexsearch, '~')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


@skip_if_on_windows
def test_repath_HOME_PATH_contents(home_env):
    exp = os.listdir(HOME_PATH)
    exp = {os.path.join(HOME_PATH, p) for p in exp}
    obs = set(pathsearch(regexsearch, '~/.*'))
    assert exp ==  obs


@skip_if_on_windows
def test_repath_HOME_PATH_var(home_env):
    exp = HOME_PATH
    obs = pathsearch(regexsearch, '$HOME')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


@skip_if_on_windows
def test_repath_HOME_PATH_var_brace(home_env):
    exp = HOME_PATH
    obs = pathsearch(regexsearch, '${"HOME"}')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


def test_helper_int(home_env):
    helper(int, 'int')

def test_helper_helper(home_env):
    helper(helper, 'helper')

def test_helper_env(home_env):
    helper(Env, 'Env')

def test_superhelper_int(home_env):
    superhelper(int, 'int')

def test_superhelper_helper(home_env):
    superhelper(helper, 'helper')

def test_superhelper_env(home_env):
    superhelper(Env, 'Env')


@pytest.mark.parametrize('exp, inp', [
    (['yo'], 'yo'),
    (['yo'], ['yo']),
    (['42'], 42),
    (['42'], [42])
])
def test_ensure_list_of_strs(exp, inp):
    obs = ensure_list_of_strs(inp)
    assert exp == obs


f = lambda x: 20
@pytest.mark.parametrize('exp, inp', [
    (['yo'], 'yo'),
    (['yo'], ['yo']),
    (['42'], 42),
    (['42'], [42]),
    ([f], f),
    ([f], [f])
])
def test_list_of_strs_or_callables(exp, inp):
    obs = list_of_strs_or_callables(inp)
    assert exp == obs


@pytest.mark.parametrize('s', [
    '~',
    '~/',
    'x=~/place',
    'x=one:~/place',
    'x=one:~/place:~/yo',
    'x=~/one:~/place:~/yo',
    ])
def test_expand_path(s, home_env):
    if os.sep != '/':
        s = s.replace('/', os.sep)
    if os.pathsep != ':':
        s = s.replace(':', os.pathsep)
    assert expand_path(s) == s.replace('~', HOME_PATH)


@pytest.mark.parametrize('kind', [str, 's', 'S', 'str', 'string'])
def test_convert_macro_arg_str(kind):
    raw_arg = 'value'
    arg = convert_macro_arg(raw_arg, kind, None, None)
    assert arg is raw_arg


@pytest.mark.parametrize('kind', [AST, 'a', 'Ast'])
def test_convert_macro_arg_ast(kind):
    raw_arg = '42'
    arg = convert_macro_arg(raw_arg, kind, {}, None)
    assert isinstance(arg, AST)


@pytest.mark.parametrize('kind', [types.CodeType, compile, 'c', 'code',
                                  'compile'])
def test_convert_macro_arg_code(kind):
    raw_arg = '42'
    arg = convert_macro_arg(raw_arg, kind, {}, None)
    assert isinstance(arg, types.CodeType)


@pytest.mark.parametrize('kind', [eval, None, 'v', 'eval'])
def test_convert_macro_arg_eval(kind):
    # literals
    raw_arg = '42'
    arg = convert_macro_arg(raw_arg, kind, {}, None)
    assert arg == 42
    # exprs
    raw_arg = 'x + 41'
    arg = convert_macro_arg(raw_arg, kind, {}, {'x': 1})
    assert arg == 42


@pytest.mark.parametrize('kind', [exec, 'x', 'exec'])
def test_convert_macro_arg_exec(kind):
    # at global scope
    raw_arg = 'def f(x, y):\n    return x + y'
    glbs = {}
    arg = convert_macro_arg(raw_arg, kind, glbs, None)
    assert arg is None
    assert 'f' in glbs
    assert glbs['f'](1, 41) == 42
    # at local scope
    raw_arg = 'def g(z):\n    return x + z\ny += 42'
    glbs = {'x': 40}
    locs = {'y': 1}
    arg = convert_macro_arg(raw_arg, kind, glbs, locs)
    assert arg is None
    assert 'g' in locs
    assert locs['g'](1) == 41
    assert 'y' in locs
    assert locs['y'] == 43


@pytest.mark.parametrize('kind', [type, 't', 'type'])
def test_convert_macro_arg_eval(kind):
    # literals
    raw_arg = '42'
    arg = convert_macro_arg(raw_arg, kind, {}, None)
    assert arg is int
    # exprs
    raw_arg = 'x + 41'
    arg = convert_macro_arg(raw_arg, kind, {}, {'x': 1})
    assert arg is int


def test_in_macro_call():
    def f():
        pass
    with in_macro_call(f, True, True):
        assert f.macro_globals
        assert f.macro_locals
    assert not hasattr(f, 'macro_globals')
    assert not hasattr(f, 'macro_locals')


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_str(arg):
    def f(x : str):
        return x
    rtn = call_macro(f, [arg], None, None)
    assert rtn is arg


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_ast(arg):
    def f(x : AST):
        return x
    rtn = call_macro(f, [arg], {}, None)
    assert isinstance(rtn, AST)


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_code(arg):
    def f(x : compile):
        return x
    rtn = call_macro(f, [arg], {}, None)
    assert isinstance(rtn, types.CodeType)


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_eval(arg):
    def f(x : eval):
        return x
    rtn = call_macro(f, [arg], {'x': 42, 'y': 0}, None)
    assert rtn == 42


@pytest.mark.parametrize('arg', ['if y:\n    pass',
                                 'if 42:\n    pass',
                                 'if x + y:\n    pass'])
def test_call_macro_exec(arg):
    def f(x : exec):
        return x
    rtn = call_macro(f, [arg], {'x': 42, 'y': 0}, None)
    assert rtn is None


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_raw_arg(arg):
    def f(x : str):
        return x
    rtn = call_macro(f, ['*', arg], {'x': 42, 'y': 0}, None)
    assert rtn == 42


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_raw_kwarg(arg):
    def f(x : str):
        return x
    rtn = call_macro(f, ['*', 'x=' + arg], {'x': 42, 'y': 0}, None)
    assert rtn == 42


@pytest.mark.parametrize('arg', ['x', '42', 'x + y'])
def test_call_macro_raw_kwargs(arg):
    def f(x : str):
        return x
    rtn = call_macro(f, ['*', '**{"x" :' + arg + '}'], {'x': 42, 'y': 0}, None)
    assert rtn == 42


def test_enter_macro():
    obj = lambda: None
    rtn = enter_macro(obj, 'wakka', True, True)
    assert obj is rtn
    assert obj.macro_block == 'wakka'
    assert obj.macro_globals
    assert obj.macro_locals

