# -*- coding: utf-8 -*-
"""Tests the xonsh replay functionality."""
from __future__ import unicode_literals, print_function
import os
import builtins
from contextlib import contextmanager

import pytest

from xonsh.tools import swap
from xonsh.shell import Shell
from xonsh.replay import Replayer

from tools import ON_DARWIN

SHELL = Shell({'PATH': []})
HISTDIR = os.path.join(os.path.dirname(__file__), 'histories')

def run_replay(re_file):
    with swap(builtins, '__xonsh_shell__', SHELL):
        with swap(builtins, '__xonsh_exit__', False):
            r = Replayer(re_file)
            hist = r.replay()
    return hist


def cleanup_replay(hist):
    fname = hist.filename
    del hist
    if os.path.isfile(fname):
        os.remove(fname)


@contextmanager
def a_replay(re_file):
    hist = run_replay(re_file)
    yield hist
    cleanup_replay(hist)


@pytest.mark.skipif(ON_DARWIN, reason='Not mac friendly')
def test_echo():
    f = os.path.join(HISTDIR, 'echo.json')
    with a_replay(f) as hist:
        assert 2 == len(hist)


@pytest.mark.skipif(ON_DARWIN, reason='also not mac friendly')
def test_reecho():
    f = os.path.join(HISTDIR, 'echo.json')
    with a_replay(f) as hist:
        assert 2 == len(hist)

@pytest.mark.skipif(ON_DARWIN, reason='also not mac friendly')
def test_simple_python():
    f = os.path.join(HISTDIR, 'simple-python.json')
    with a_replay(f) as hist:
        assert 4 == len(hist)
        assert "print('The Turtles')" == hist.inps[0].strip()
