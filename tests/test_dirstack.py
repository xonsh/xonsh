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


def test_simple(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(CDPATH=PARENT, PWD=PARENT)
    with chdir(PARENT):
        assert os.getcwd() !=  HERE
        dirstack.cd(["tests"])
        assert os.getcwd() ==  HERE


def test_cdpath_simple(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(CDPATH=PARENT, PWD=HERE)
    with chdir(os.path.normpath("/")):
        assert os.getcwd() !=  HERE
        dirstack.cd(["tests"])
        assert os.getcwd() ==  HERE


def test_cdpath_collision(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(CDPATH=PARENT, PWD=HERE)
    sub_tests = os.path.join(HERE, "tests")
    if not os.path.exists(sub_tests):
        os.mkdir(sub_tests)
    with chdir(HERE):
        assert os.getcwd() ==  HERE
        dirstack.cd(["tests"])
        assert os.getcwd() ==  os.path.join(HERE, "tests")


def test_cdpath_expansion(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(HERE=HERE, CDPATH=("~", "$HERE"))
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


def test_uncpushd_no_map_when_no_unc_check(xonsh_builtins):
    pass


def test_uncpushd_simple_push_pop(xonsh_builtins):
    pass


def test_uncpushd_push_to_same_share(xonsh_builtins):
    pass


def test_uncpushd_push_twice_to_same(xonsh_builtins):
    """push twice to same share, then pop twice.  Verify drive not unmapped till 2nd pop"""
    pass


def test_uncpushd_push_other_push_same(xonsh_builtins):
    """push to a, then to b, then to a again. Pop (check a still mapped), pop, pop (check a is unmapped)"""
    pass




