"""Tests the xonsh history."""
from __future__ import unicode_literals, print_function
import os

import nose
from nose.tools import assert_equal, assert_true

from xonsh.history import History
from xonsh.lazyjson import LazyJSON

HIST_TEST_KWARGS = dict(sessionid='SESSIONID', gc=False)


def test_hist_init():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.init'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with LazyJSON(FNAME, reopen=False) as lj:
        obs = lj['here']
    assert_equal('yup', obs)
    os.remove(FNAME)


def test_hist_append():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.append'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    hf = hist.append({'joco': 'still alive'})
    yield assert_true, hf is None
    yield assert_equal, 'still alive', hist.buffer[0]['joco']
    os.remove(FNAME)


def test_hist_flush():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.flush'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
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
    os.remove(FNAME)



if __name__ == '__main__':
    nose.runmodule()
