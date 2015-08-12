"""Tests the xonsh history."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true, assert_not_in

from xonsh.history import History
from xonsh.lazyjson import LazyJSON

FNAME = 'xonsh-SESSIONID.json'
HIST_TEST_KWARGS = dict(filename=FNAME, sessionid='SESSIONID', gc=False)


def teardown():
    if os.path.isfile(FNAME):
        os.remove(FNAME)


def test_hist_init():
    hist = History(here='yup', **HIST_TEST_KWARGS)
    with LazyJSON(FNAME, reopen=False) as lj:
        obs = lj['here']
    assert_equal('yup', obs)
    with open(FNAME) as f:
        s = f.read()
    print(s)


def test_hist_append():
    hist = History(here='yup', **HIST_TEST_KWARGS)
    hf = hist.append({'joco': 'still alive'})
    yield assert_true, hf is None
    yield assert_equal, 'still alive', hist.buffer[0]['joco']


def test_hist_flush():
    hist = History(here='yup', **HIST_TEST_KWARGS)
    hf = hist.flush()
    yield assert_true, hf is None
    hist.append({'joco': 'still alive'})
    hf = hist.flush()
    yield assert_true, hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(FNAME, reopen=False) as lj:
        obs = lj['cmds'][0]['joco']
    yield assert_equal, 'still alive', obs



if __name__ == '__main__':
    nose.runmodule()
