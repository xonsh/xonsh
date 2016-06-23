# -*- coding: utf-8 -*-
"""Testing xonsh import hooks"""
from __future__ import unicode_literals, print_function

from xonsh import imphooks  # noqa
from xonsh import built_ins
from xonsh.execer import Execer
from xonsh.built_ins import load_builtins, unload_builtins

from tools import mock_xonsh_env
LOADED_HERE = False

IMP_ENV = {'PATH': [], 'PATHEXT': []}

def setup_module():
    global LOADED_HERE
    if built_ins.BUILTINS_LOADED:
        unload_builtins()  # make sure we have a clean env from other tests.
        load_builtins(execer=Execer())
        LOADED_HERE = True

def teardown_module():
    if LOADED_HERE:
        unload_builtins()

def test_import():
    with mock_xonsh_env(IMP_ENV):
        import sample
        assert ('hello mom jawaka\n' == sample.x)

def test_absolute_import():
    with mock_xonsh_env(IMP_ENV):
        from xpack import sample
        assert ('hello mom jawaka\n' == sample.x)

def test_relative_import():
    with mock_xonsh_env(IMP_ENV):
        from xpack import relimp
        assert ('hello mom jawaka\n' == relimp.sample.x)
        assert ('hello mom jawaka\ndark chest of wonders' == relimp.y)

def test_sub_import():
    with mock_xonsh_env(IMP_ENV):
        from xpack.sub import sample
        assert ('hello mom jawaka\n' == sample.x)
