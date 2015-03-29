"""Testing xonsh import hooks"""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

from xonsh import imphooks

def test_relative_import():
    import sample
    assert_equal('hello mom\n', sample.x)

if __name__ == '__main__':
    nose.runmodule()
