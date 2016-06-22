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
from xonsh.tools import ON_WINDOWS

from tools import mock_xonsh_env


def test_reglob_tests():
    testfiles = reglob('test_.*')
    for f in testfiles:
        assert (f.startswith('test_'))

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_repath_backslash():
    home = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=home)
    with mock_xonsh_env(built_ins.ENV):
        exp = os.listdir(home)
        exp = {p for p in exp if re.match(r'\w\w.*', p)}
        exp = {os.path.join(home, p) for p in exp}
        obs = set(pathsearch(regexsearch, r'~/\w\w.*'))
        assert exp ==  obs

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_repath_home_itself():
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = pathsearch(regexsearch, '~')
        assert 1 ==  len(obs)
        assert exp ==  obs[0]

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_repath_home_contents():
    home = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=home)
    with mock_xonsh_env(built_ins.ENV):
        exp = os.listdir(home)
        exp = {os.path.join(home, p) for p in exp}
        obs = set(pathsearch(regexsearch, '~/.*'))
        assert exp ==  obs

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_repath_home_var():
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = pathsearch(regexsearch, '$HOME')
        assert 1 ==  len(obs)
        assert exp ==  obs[0]

@pytest.mark.skipif(ON_WINDOWS, reason='Unix stuff')
def test_repath_home_var_brace():
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = pathsearch(regexsearch, '${"HOME"}')
        assert 1 ==  len(obs)
        assert exp ==  obs[0]

def test_helper_int():
    with mock_xonsh_env({}):
        helper(int, 'int')

def test_helper_helper():
    with mock_xonsh_env({}):
        helper(helper, 'helper')

def test_helper_env():
    with mock_xonsh_env({}):
        helper(Env, 'Env')

def test_superhelper_int():
    with mock_xonsh_env({}):
        superhelper(int, 'int')

def test_superhelper_helper():
    with mock_xonsh_env({}):
        superhelper(helper, 'helper')

def test_superhelper_env():
    with mock_xonsh_env({}):
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
