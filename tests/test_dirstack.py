# -*- coding: utf-8 -*-
"""Testing dirstack"""
from __future__ import unicode_literals, print_function

from contextlib import contextmanager
from functools import wraps
import os
import builtins

import pytest

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

@pytest.mark.skip(reason='BUG')
def test_simple():
    load_builtins()
    with xonsh_env(Env(CDPATH=PARENT, PWD=PARENT)):
        with chdir(PARENT):
            assert os.getcwd() !=  HERE
            dirstack.cd(["tests"])
            assert os.getcwd() ==  HERE

@pytest.mark.skip(reason='BUG')
def test_cdpath_simple():
    with xonsh_env(Env(CDPATH=PARENT, PWD=HERE)):
        with chdir(os.path.normpath("/")):
            assert os.getcwd() !=  HERE
            dirstack.cd(["tests"])
            assert os.getcwd() ==  HERE

@pytest.mark.skip(reason='BUG')
def test_cdpath_collision():
    with xonsh_env(Env(CDPATH=PARENT, PWD=HERE)):
        sub_tests = os.path.join(HERE, "tests")
        if not os.path.exists(sub_tests):
            os.mkdir(sub_tests)
        with chdir(HERE):
            assert os.getcwd() ==  HERE
            dirstack.cd(["tests"])
            assert os.getcwd() ==  os.path.join(HERE, "tests")

def test_cdpath_expansion():
    with xonsh_env(Env(HERE=HERE, CDPATH=("~", "$HERE"))):
        test_dirs = (
            os.path.join(HERE, "xonsh-test-cdpath-here"),
            os.path.expanduser("~/xonsh-test-cdpath-home")
        )
        try:
            for _ in test_dirs:
                if not os.path.exists(_):
                    os.mkdir(_)
                assert os.path.exists(dirstack._try_cdpath(_)), "dirstack._try_cdpath: could not resolve {0}".format(_)
        except Exception as e:
            tuple(os.rmdir(_) for _ in test_dirs if os.path.exists(_))
            raise e
