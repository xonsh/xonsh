# -*- coding: utf-8 -*-
"""Testing xonsh import hooks"""
import os
import builtins

import pytest

from xonsh import imphooks
from xonsh.execer import Execer
from xonsh.environ import Env
from xonsh.built_ins import unload_builtins

imphooks.install_import_hooks()


@pytest.fixture(autouse=True)
def imp_env(xonsh_builtins):
    execer = Execer(unload=False)
    builtins.__xonsh__.env = Env({"PATH": [], "PATHEXT": []})
    yield
    unload_builtins()


def test_import():
    import sample

    assert "hello mom jawaka\n" == sample.x


def test_absolute_import():
    from xpack import sample

    assert "hello mom jawaka\n" == sample.x


def test_relative_import():
    from xpack import relimp

    assert "hello mom jawaka\n" == relimp.sample.x
    assert "hello mom jawaka\ndark chest of wonders" == relimp.y


def test_sub_import():
    from xpack.sub import sample

    assert "hello mom jawaka\n" == sample.x


TEST_DIR = os.path.dirname(__file__)


def test_module_dunder_file_attribute():
    import sample

    exp = os.path.join(TEST_DIR, "sample.xsh")
    assert os.path.abspath(sample.__file__) == exp


def test_module_dunder_file_attribute_sub():
    from xpack.sub import sample

    exp = os.path.join(TEST_DIR, "xpack", "sub", "sample.xsh")
    assert os.path.abspath(sample.__file__) == exp
