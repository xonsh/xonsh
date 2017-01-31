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
        assert os.getcwd() == HERE
        dirstack.cd(["tests"])
        assert os.getcwd() ==  os.path.join(HERE, "tests")


def test_cdpath_expansion(xonsh_builtins):
    xonsh_builtins.__xonsh_env__ = Env(HERE=HERE, CDPATH=("~", "$HERE"))
    test_dirs = (
        os.path.join(HERE, "xonsh-test-cdpath-here"),
        os.path.expanduser("~/xonsh-test-cdpath-home")
    )
    try:
        for d in test_dirs:
            if not os.path.exists(d):
                os.mkdir(d)
            assert os.path.exists(dirstack._try_cdpath(d)), "dirstack._try_cdpath: could not resolve {0}".format(d)
    finally:
        for d in test_dirs:
            if os.path.exists(d):
                os.rmdir(d)


def test_cdpath_events(xonsh_builtins, tmpdir):
    xonsh_builtins.__xonsh_env__ = Env(CDPATH=PARENT, PWD=os.getcwd())
    target = str(tmpdir)

    ev = None
    @xonsh_builtins.events.on_chdir
    def handler(olddir, newdir, **kw):
        nonlocal ev
        ev = olddir, newdir

    old_dir = os.getcwd()
    try:
        dirstack.cd([target])
    except:
        raise
    else:
        assert (old_dir, target) == ev
    finally:
        # Use os.chdir() here so dirstack.cd() doesn't fire events (or fail again)
        os.chdir(old_dir)


def test_cd_autopush(xonsh_builtins, tmpdir):
    xonsh_builtins.__xonsh_env__ = Env(CDPATH=PARENT, PWD=os.getcwd(), AUTO_PUSHD=True)
    target = str(tmpdir)

    old_dir = os.getcwd()
    old_ds_size = len(dirstack.DIRSTACK)

    assert target != old_dir

    try:
        dirstack.cd([target])
        assert target == os.getcwd()
        assert old_ds_size + 1 == len(dirstack.DIRSTACK)
        dirstack.popd([])
    except:
        raise
    finally:
        while len(dirstack.DIRSTACK) > old_ds_size:
            dirstack.popd([])

    assert old_dir == os.getcwd()
