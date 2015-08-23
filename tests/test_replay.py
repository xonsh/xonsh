"""Tests the xonsh replay functionality."""
from __future__ import unicode_literals, print_function
import os
import builtins
from contextlib import contextmanager

import nose
from nose.tools import assert_equal, assert_true

from xonsh.tools import swap
from xonsh.shell import Shell
from xonsh.replay import Replayer

SHELL = Shell()
HISTDIR = os.path.join(os.path.dirname(__file__), 'histories')

def run_replay(re_file):
    with swap(builtins, '__xonsh_shell__', SHELL):
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


def test_echo():
    f = os.path.join(HISTDIR, 'echo.json')
    with a_replay(f) as hist:
        yield assert_equal, 2, len(hist)


def test_reecho():
    f = os.path.join(HISTDIR, 'echo.json')
    with a_replay(f) as hist:
        yield assert_equal, 2, len(hist)


if __name__ == '__main__':
    nose.runmodule()
