"""Testing dirstack"""
from __future__ import unicode_literals, print_function

from contextlib import contextmanager
from functools import wraps
import os
import builtins

from nose.tools import assert_equal, assert_not_equal
import nose

from xonsh import dirstack
from xonsh.environ import Env
from xonsh.built_ins import load_builtins


HERE = os.path.abspath(os.path.dirname(__file__))
PARENT = os.path.dirname(HERE)

@contextmanager
def chdir(adir):
    old_dir = os.getcwd()
    os.chdir(adir)
    yield
    os.chdir(old_dir)

@contextmanager
def xonsh_env(env):
    load_builtins()
    old_env = builtins.__xonsh_env__
    builtins.__xonsh_env__ = env
    yield
    builtins.__xonsh_env__ = old_env

def test_simple():
    load_builtins()
    with chdir(PARENT):
        assert_not_equal(os.getcwd(), HERE)
        dirstack.cd(["tests"])
        assert_equal(os.getcwd(), HERE)

def test_cdpath_simple():
    with xonsh_env(Env(CDPATH=PARENT)):
        with chdir(os.path.normpath("/")):
            assert_not_equal(os.getcwd(), HERE)
            dirstack.cd(["tests"])
            assert_equal(os.getcwd(), HERE)

def test_cdpath_collision():
    with xonsh_env(Env(CDPATH=PARENT)):
        sub_tests = os.path.join(HERE, "tests")
        if not os.path.exists(sub_tests):
            os.mkdir(sub_tests)
        with chdir(HERE):
            assert_equal(os.getcwd(), HERE)
            dirstack.cd(["tests"])
            assert_equal(os.getcwd(), os.path.join(HERE, "tests"))


if __name__ == '__main__':
    nose.runmodule()
