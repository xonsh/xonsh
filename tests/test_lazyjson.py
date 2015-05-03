"""Tests lazy json functionality."""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

from xonsh.lazyjson import index

def test_index_int():
    exp = {'offset': 0, 'size': 2}
    s, obs = index(42)
    assert_equal(exp, obs)

def test_index_str():
    exp = {'offset': 0, 'size': 7}
    s, obs = index('wakka')
    assert_equal(exp, obs)

def test_index_list_ints():
    exp = {'offset': [1, 4], 'size': [1, 2]}
    s, obs = index([1, 42])
    assert_equal(exp, obs)

def test_index_list_str():
    exp = {'offset': [1, 10], 'size': [7, 8]}
    s, obs = index(['wakka', 'jawaka'])
    assert_equal(exp, obs)

def test_index_list_str_int():
    exp = {'offset': [1, 10], 'size': [7, 2]}
    s, obs = index(['wakka', 42])
    assert_equal(exp, obs)

def test_index_list_int_str():
    exp = {'offset': [1, 5, 14], 'size': [2, 7, 8]}
    s, obs = index([42, 'wakka', 'jawaka'])
    assert_equal(exp, obs)



if __name__ == '__main__':
    nose.runmodule()
