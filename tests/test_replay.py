# -*- coding: utf-8 -*-
"""Tests the xonsh replay functionality."""
import os
import builtins

import pytest

from xonsh.shell import Shell
from xonsh.execer import Execer
from xonsh.replay import Replayer

from tools import skip_if_on_darwin


HISTDIR = os.path.join(os.path.dirname(__file__), 'histories')


@pytest.yield_fixture(scope='module', autouse=True)
def ctx():
    """Create a global Shell instance to use in all the test."""
    ctx = {'PATH': []}
    execer = Execer(xonsh_ctx=ctx)
    builtins.__xonsh_shell__ = Shell(execer=execer, ctx=ctx, shell_type='none')
    yield
    del builtins.__xonsh_shell__


@skip_if_on_darwin
def test_echo():
    histfile = os.path.join(HISTDIR, 'echo.json')
    hist = Replayer(histfile).replay()
    assert len(hist) == 2


@skip_if_on_darwin
def test_reecho():
    histfile = os.path.join(HISTDIR, 'echo.json')
    hist = Replayer(histfile).replay()
    assert len(hist) == 2


@skip_if_on_darwin
def test_simple_python():
    histfile = os.path.join(HISTDIR, 'simple-python.json')
    hist = Replayer(histfile).replay()
    assert len(hist) == 4
    assert hist.inps[0].strip() == "print('The Turtles')"
