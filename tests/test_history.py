"""Tests the xonsh history."""
from __future__ import unicode_literals, print_function
import io
import os
import sys

import nose
from nose.tools import assert_equal, assert_true

from xonsh.lazyjson import LazyJSON
from xonsh.history import History, CommandField
from xonsh import history

HIST_TEST_KWARGS = dict(sessionid='SESSIONID', gc=False)


def test_hist_init():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.init'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with LazyJSON(FNAME) as lj:
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
    with LazyJSON(FNAME) as lj:
        obs = lj['cmds'][0]['joco']
    yield assert_equal, 'still alive', obs
    os.remove(FNAME)


def test_cmd_field():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.cmdfield'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    # in-memory
    hf = hist.append({'rtn': 1})
    yield assert_true, hf is None
    yield assert_equal, 1, hist.rtns[0]
    yield assert_equal, 1, hist.rtns[-1]
    yield assert_equal, None, hist.outs[-1]
    # slice
    yield assert_equal, [1], hist.rtns[:]
    # on disk
    hf = hist.flush()
    yield assert_true, hf is not None
    yield assert_equal, 1, hist.rtns[0]
    yield assert_equal, 1, hist.rtns[-1]
    yield assert_equal, None, hist.outs[-1]
    os.remove(FNAME)

def test_show_cmd():
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.show_cmd'
    cmds = ['ls', 'cat hello kitty', 'abc', 'def', 'touch me', 'grep from me']

    def format_hist_line(idx, cmd):
        return ' {:d}  {:s}\n'.format(idx, cmd)

    def run_show_cmd(hist_args, commands, base_idx=0, step=1):
        stdout.seek(0, io.SEEK_SET)
        stdout.truncate()
        history.main(hist_args, hist=hist)
        stdout.seek(0, io.SEEK_SET)
        hist_lines = stdout.readlines()
        yield assert_equal, len(commands), len(hist_lines)
        for idx, (cmd, actual) in enumerate(zip(commands, hist_lines)):
            expected = format_hist_line(base_idx + idx * step, cmd)
            yield assert_equal, expected, actual

    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    stdout = io.StringIO()
    saved_stdout = sys.stdout
    sys.stdout = stdout

    for cmd in cmds: # populate the shell history
        hist.append({'inp': cmd, 'rtn': 0})

    # Verify an implicit "show" emits the entire history.
    for x in run_show_cmd([], cmds):
        yield x

    # Verify an explicit "show" with no qualifiers emits the entire history.
    for x in run_show_cmd(['show'], cmds):
        yield x

    # Verify an explicit "show" with a reversed qualifier emits the entire
    # history in reverse order.
    for x in run_show_cmd(['show', '-r'], list(reversed(cmds)),
                         len(cmds) - 1, -1):
        yield x

    # Verify that showing a specific history entry relative to the start of the
    # history works.
    for x in run_show_cmd(['show', '0'], [cmds[0]], 0):
        yield x
    for x in run_show_cmd(['show', '1'], [cmds[1]], 1):
        yield x

    # Verify that showing a specific history entry relative to the end of the
    # history works.
    for x in run_show_cmd(['show', '-2'], [cmds[-2]], len(cmds) - 2):
        yield x

    # Verify that showing a history range relative to the start of the
    # history works.
    for x in run_show_cmd(['show', '0:2'], cmds[0:2], 0):
        yield x
    for x in run_show_cmd(['show', '1::2'], cmds[1::2], 1, 2):
        yield x

    # Verify that showing a history range relative to the end of the
    # history works.
    for x in run_show_cmd(['show', '-2:'], cmds[-2:], len(cmds) - 2):
        yield x
    for x in run_show_cmd(['show', '-4:-2'], cmds[-4:-2], len(cmds) - 4):
        yield x

    sys.stdout = saved_stdout
    os.remove(FNAME)

if __name__ == '__main__':
    nose.runmodule()
