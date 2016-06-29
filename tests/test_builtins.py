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


def test_reglob_tests():
    testfiles = reglob('test_.*')
    for f in testfiles:
        assert (f.startswith('test_'))

# @pytest.fixture
# def env():
#     e = Env(HOME=os.path.expanduser('~'))
#     built_ins.ENV = e
#     return e


@skip_if_on_windows
@pytest.mark.parametrize('xenv', [Env(HOME=HOME_PATH)])
def test_repath_backslash(xonsh_env):
    exp = os.listdir(HOME_PATH)
    exp = {p for p in exp if re.match(r'\w\w.*', p)}
    exp = {os.path.join(HOME_PATH, p) for p in exp}
    obs = set(pathsearch(regexsearch, r'~/\w\w.*'))
    assert exp ==  obs

@skip_if_on_windows
@pytest.mark.parametrize('xenv', [Env(HOME=os.path.expanduser('~'))])
def test_repath_HOME_PATH_itself(xonsh_env):
    obs = pathsearch(regexsearch, '~')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


@skip_if_on_windows
@pytest.mark.parametrize('xenv', [Env(HOME=os.path.expanduser('~'))])
def test_repath_HOME_PATH_contents(xonsh_env):
    exp = os.listdir(HOME_PATH)
    exp = {os.path.join(HOME_PATH, p) for p in exp}
    obs = set(pathsearch(regexsearch, '~/.*'))
    assert exp ==  obs


@skip_if_on_windows
@pytest.mark.parametrize('xenv', [Env(HOME=os.path.expanduser('~'))])
def test_repath_HOME_PATH_var(xonsh_env):
    obs = pathsearch(regexsearch, '$HOME')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


@skip_if_on_windows
@pytest.mark.parametrize('xenv', [Env(HOME=os.path.expanduser('~'))])
def test_repath_HOME_PATH_var_brace(xonsh_env):
    obs = pathsearch(regexsearch, '${"HOME"}')
    assert 1 ==  len(obs)
    assert exp ==  obs[0]


def test_helper_int(xonsh_env):
    helper(int, 'int')

def test_helper_helper(xonsh_env):
    helper(helper, 'helper')

def test_helper_env(xonsh_env):
    helper(Env, 'Env')

def test_superhelper_int(xonsh_env):
    superhelper(int, 'int')

def test_superhelper_helper(xonsh_env):
    superhelper(helper, 'helper')

def test_superhelper_env(xonsh_env):
    superhelper(Env, 'Env')

def test_ensure_list_of_strs():
    cases = [(['yo'], 'yo'), (['yo'], ['yo']), (['42'], 42), (['42'], [42])]
    for exp, inp in cases:
        obs = ensure_list_of_strs(inp)
        assert exp == obs

def test_list_of_strs_or_callables():
    f = lambda x: 20
    cases = [(['yo'], 'yo'), (['yo'], ['yo']), (['42'], 42), (['42'], [42]),
             ([f], f), ([f], [f])]
    for exp, inp in cases:
        obs = list_of_strs_or_callables(inp)
        assert exp == obs
