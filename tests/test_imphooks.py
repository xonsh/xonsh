# -*- coding: utf-8 -*-
"""Testing xonsh import hooks"""
from __future__ import unicode_literals, print_function

import nose
from nose.tools import assert_equal

from xonsh import imphooks  # noqa
from xonsh import built_ins
from xonsh.execer import Execer
from xonsh.built_ins import load_builtins, unload_builtins

from tests.tools import mock_xonsh_env
LOADED_HERE = False

def setup():
    global LOADED_HERE
    if built_ins.BUILTINS_LOADED:
        unload_builtins()  # make sure we have a clean env from other tests.
        load_builtins(execer=Execer())
        LOADED_HERE = True

def teardown():
    if LOADED_HERE:
        unload_builtins()

def test_import():
    with mock_xonsh_env({}):
        import sample
        assert_equal('hello mom jawaka\n', sample.x)

def test_absolute_import():
    with mock_xonsh_env({}):
        from xpack import sample
        assert_equal('hello mom jawaka\n', sample.x)

def test_relative_import():
    with mock_xonsh_env({}):
        from xpack import relimp
        assert_equal('hello mom jawaka\n', relimp.sample.x)
        assert_equal('hello mom jawaka\ndark chest of wonders', relimp.y)

def test_sub_import():
    with mock_xonsh_env({}):
        from xpack.sub import sample
        assert_equal('hello mom jawaka\n', sample.x)


if __name__ == '__main__':
    nose.runmodule()
