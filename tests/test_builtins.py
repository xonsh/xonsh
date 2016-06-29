# -*- coding: utf-8 -*-
"""Tests the xonsh builtins."""
from __future__ import unicode_literals, print_function
import os
import re

import pytest

from xonsh import built_ins
from xonsh.built_ins import reglob, pathsearch, helper, superhelper, \
    ensure_list_of_strs, list_of_strs_or_callables, regexsearch, \
    globsearch
from xonsh.environ import Env

from tools import skip_if_on_windows


HOME_PATH = os.path.expanduser('~')


@pytest.mark.parametrize('testfile', [*reglob('test_.*')])
def test_reglob_tests(testfile):
    assert (testfile.startswith('test_'))


@pytest.fixture
def home_env(xonsh_builtins):
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
