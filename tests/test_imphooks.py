# -*- coding: utf-8 -*-
"""Testing xonsh import hooks"""
import pytest

from xonsh import imphooks  # noqa
from xonsh import built_ins
from xonsh.environ import Env
from xonsh.execer import Execer
from xonsh.built_ins import load_builtins, unload_builtins
import builtins


@pytest.yield_fixture(autouse=True)
def imp_env(xonsh_execer):
    """Call `load_builtins with `xonsh_execer`"""
    load_builtins(execer=xonsh_execer)
    builtins.__xonsh_env__ = Env({'PATH': [], 'PATHEXT': []})
    yield
    unload_builtins()


def test_import():
    import sample
    assert ('hello mom jawaka\n' == sample.x)


def test_absolute_import():
    from xpack import sample
    assert ('hello mom jawaka\n' == sample.x)


def test_relative_import():
    from xpack import relimp
    assert ('hello mom jawaka\n' == relimp.sample.x)
    assert ('hello mom jawaka\ndark chest of wonders' == relimp.y)


def test_sub_import():
    from xpack.sub import sample
    assert ('hello mom jawaka\n' == sample.x)
