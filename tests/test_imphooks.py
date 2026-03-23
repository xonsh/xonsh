"""Testing xonsh import hooks"""

import os
from importlib import import_module

import pytest

from xonsh import imphooks
from xonsh.pytest.tools import ON_WINDOWS


@pytest.fixture(autouse=True)
def imp_env(xession):
    xession.env.update({"PATH": [], "PATHEXT": []})
    imphooks.install_import_hooks(xession.execer)
    yield

def check_out(out):
    if ON_WINDOWS:
        # Windows `echo` (`cmd /c echo`) keeps quotes in case of using space.
        assert '"hello mom" jawaka\n' == out
    else:
        assert "hello mom jawaka\n" == out


def test_import():
    import sample
    check_out(sample.x)


def test_import_empty():
    from xpack import empty_xsh

    assert empty_xsh


def test_absolute_import():
    from xpack import sample
    check_out(sample.x)


def test_relative_import():
    from xpack import relimp
    check_out(relimp.sample.x)

    first, second = relimp.y.split('\n')
    check_out(first+'\n')
    assert "dark chest of wonders" == second


def test_sub_import():
    from xpack.sub import sample
    check_out(sample.x)


TEST_DIR = os.path.dirname(__file__)


def test_module_dunder_file_attribute():
    import sample

    exp = os.path.join(TEST_DIR, "sample.xsh")
    assert os.path.abspath(sample.__file__) == exp


def test_module_dunder_file_attribute_sub():
    from xpack.sub import sample

    exp = os.path.join(TEST_DIR, "xpack", "sub", "sample.xsh")
    assert os.path.abspath(sample.__file__) == exp


def test_get_source():
    mod = import_module("sample")
    loader = mod.__loader__
    source = loader.get_source("sample")
    with open(os.path.join(TEST_DIR, "sample.xsh")) as srcfile:
        assert source == srcfile.read()
