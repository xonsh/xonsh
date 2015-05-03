"""Tests lazy json functionality."""
from __future__ import unicode_literals, print_function
from io import StringIO

import nose
from nose.tools import assert_equal
assert_equal.__self__.maxDiff = None

from xonsh.lazyjson import index, dump, LazyJSON

def test_index_int():
    exp = {'offsets': 0, 'sizes': 2}
    s, obs = index(42)
    assert_equal(exp, obs)

def test_index_str():
    exp = {'offsets': 0, 'sizes': 7}
    s, obs = index('wakka')
    assert_equal(exp, obs)

def test_index_list_ints():
    exp = {'offsets': [1, 4, 0], 'sizes': [1, 2, 8]}
    s, obs = index([1, 42])
    assert_equal(exp, obs)

def test_index_list_str():
    exp = {'offsets': [1, 10, 0], 'sizes': [7, 8, 20]}
    s, obs = index(['wakka', 'jawaka'])
    assert_equal(exp, obs)

def test_index_list_str_int():
    exp = {'offsets': [1, 10, 0], 'sizes': [7, 2, 14]}
    s, obs = index(['wakka', 42])
    assert_equal(exp, obs)

def test_index_list_int_str():
    exp = {'offsets': [1, 5, 14, 0], 'sizes': [2, 7, 8, 24]}
    s, obs = index([42, 'wakka', 'jawaka'])
    assert_equal(exp, obs)

def test_index_dict_int():
    exp = {'offsets': {'wakka': 10, '__total__': 0}, 
           'sizes': {'wakka': 2, '__total__': 14}}
    s, obs = index({'wakka': 42})
    assert_equal(exp, obs)

def test_index_dict_str():
    exp = {'offsets': {'wakka': 10, '__total__': 0}, 
           'sizes': {'wakka': 8, '__total__': 20}}
    s, obs = index({'wakka': 'jawaka'})
    assert_equal(exp, obs)

def test_index_dict_dict_int():
    exp = {'offsets': {'wakka': {'jawaka': 21, '__total__': 10},
                      '__total__': 0,
                      },
           'sizes': {'wakka': {'jawaka': 2, '__total__': 15}, 
                    '__total__': 27}
           }
    s, obs = index({'wakka': {'jawaka': 42}})
    assert_equal(exp, obs)

def test_lazy_load_index():
    f = StringIO()
    dump({'wakka': 42}, f)
    f.seek(0)
    lj = LazyJSON(f)
    assert_equal({'wakka': 10, '__total__': 0}, lj.offsets)
    assert_equal({'wakka': 2, '__total__': 14}, lj.sizes)

if __name__ == '__main__':
    nose.runmodule()
