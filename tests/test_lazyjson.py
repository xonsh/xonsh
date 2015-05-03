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
    exp = {'offset': [1, 3], 'size': [1, 2]}
    s, obs = index([1, 42])
    print(s)
    assert_equal(exp, obs)


if __name__ == '__main__':
    nose.runmodule()
