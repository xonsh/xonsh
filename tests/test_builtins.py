# -*- coding: utf-8 -*-
"""Tests the xonsh builtins."""
from __future__ import unicode_literals, print_function
import os
import re

import nose
from nose.plugins.skip import SkipTest
from nose.tools import assert_equal, assert_true, assert_not_in

from xonsh import built_ins
from xonsh.built_ins import reglob, regexpath, helper, superhelper, \
    ensure_list_of_strs, expand_case_matching
from xonsh.environ import Env
from xonsh.tools import ON_WINDOWS

from tools import mock_xonsh_env


def test_reglob_tests():
    testfiles = reglob('test_.*')
    for f in testfiles:
        assert_true(f.startswith('test_'))

def test_repath_backslash():
    if ON_WINDOWS:
        raise SkipTest
    home = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=home)
    with mock_xonsh_env(built_ins.ENV):
        exp = os.listdir(home)
        exp = {p for p in exp if re.match(r'\w\w.*', p)}
        exp = {os.path.join(home, p) for p in exp}
        obs = set(regexpath(r'~/\w\w.*'))
        assert_equal(exp, obs)

def test_repath_home_itself():
    if ON_WINDOWS:
        raise SkipTest
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = regexpath('~')
        assert_equal(1, len(obs))
        assert_equal(exp, obs[0])

def test_repath_home_contents():
    if ON_WINDOWS:
        raise SkipTest
    home = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=home)
    with mock_xonsh_env(built_ins.ENV):
        exp = os.listdir(home)
        exp = {os.path.join(home, p) for p in exp}
        obs = set(regexpath('~/.*'))
        assert_equal(exp, obs)

def test_repath_home_var():
    if ON_WINDOWS:
        raise SkipTest
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = regexpath('$HOME')
        assert_equal(1, len(obs))
        assert_equal(exp, obs[0])

def test_repath_home_var_brace():
    if ON_WINDOWS:
        raise SkipTest
    exp = os.path.expanduser('~')
    built_ins.ENV = Env(HOME=exp)
    with mock_xonsh_env(built_ins.ENV):
        obs = regexpath('${"HOME"}')
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

def test_expand_case_matching():
    cases = {
        'yo': '[Yy][Oo]',
        '[a-f]123e': '[a-f]123[Ee]',
        '${HOME}/yo': '${HOME}/[Yy][Oo]',
        './yo/mom': './[Yy][Oo]/[Mm][Oo][Mm]',
        'Eßen': '[Ee][Ss]?[Ssß][Ee][Nn]',
        }
    for inp, exp in cases.items():
        obs = expand_case_matching(inp)
        yield assert_equal, exp, obs


if __name__ == '__main__':
    nose.runmodule()
