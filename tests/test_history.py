# -*- coding: utf-8 -*-
"""Tests the xonsh history."""
# pylint: disable=protected-access
# TODO: Remove the following pylint directive when it correctly handles calls
# to nose assert_xxx functions.
# pylint: disable=no-value-for-parameter
from __future__ import unicode_literals, print_function
import io
import os
import sys

import nose
from nose.tools import assert_equal, assert_is_none, assert_is_not_none

from xonsh.lazyjson import LazyJSON
from xonsh.history import History
from xonsh import history

from tests.tools import mock_xonsh_env

HIST_TEST_KWARGS = dict(sessionid='SESSIONID', gc=False)


def test_hist_init():
    """Test initialization of the shell history."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.init'
    History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with LazyJSON(FNAME) as lj:
        obs = lj['here']
    assert_equal('yup', obs)
    os.remove(FNAME)


def test_hist_append():
    """Verify appending to the history works."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.append'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hf = hist.append({'joco': 'still alive'})
    yield assert_is_none, hf
    yield assert_equal, 'still alive', hist.buffer[0]['joco']
    os.remove(FNAME)


def test_hist_flush():
    """Verify explicit flushing of the history works."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.flush'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    hf = hist.flush()
    yield assert_is_none, hf
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hist.append({'joco': 'still alive'})
    hf = hist.flush()
    yield assert_is_not_none, hf
    while hf.is_alive():
        pass
    with LazyJSON(FNAME) as lj:
        obs = lj['cmds'][0]['joco']
    yield assert_equal, 'still alive', obs
    os.remove(FNAME)


def test_cmd_field():
    """Test basic history behavior."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.cmdfield'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    # in-memory
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hf = hist.append({'rtn': 1})
    yield assert_is_none, hf
    yield assert_equal, 1, hist.rtns[0]
    yield assert_equal, 1, hist.rtns[-1]
    yield assert_equal, None, hist.outs[-1]
    # slice
    yield assert_equal, [1], hist.rtns[:]
    # on disk
    hf = hist.flush()
    yield assert_is_not_none, hf
    yield assert_equal, 1, hist.rtns[0]
    yield assert_equal, 1, hist.rtns[-1]
    yield assert_equal, None, hist.outs[-1]
    os.remove(FNAME)


def test_show_cmd():
    """Verify that CLI history commands work."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.show_cmd'
    cmds = ['ls', 'cat hello kitty', 'abc', 'def', 'touch me', 'grep from me']

    def format_hist_line(idx, cmd):
        """Construct a history output line."""
        return ' {:d}  {:s}\n'.format(idx, cmd)

    def run_show_cmd(hist_args, commands, base_idx=0, step=1):
        """Run and evaluate the output of the given show command."""
        stdout.seek(0, io.SEEK_SET)
        stdout.truncate()
        history._main(hist, hist_args)
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

    with mock_xonsh_env({'HISTCONTROL': set()}):
        for cmd in cmds:  # populate the shell history
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

def test_histcontrol():
    """Test HISTCONTROL=ignoredups,ignoreerr"""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.append'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)

    with mock_xonsh_env({'HISTCONTROL': 'ignoredups,ignoreerr'}):
        yield assert_equal, len(hist.buffer), 0

        # An error, buffer remains empty
        hist.append({'inp': 'ls foo', 'rtn': 2})
        yield assert_equal, len(hist.buffer), 0

        # Success
        hist.append({'inp': 'ls foobazz', 'rtn': 0})
        yield assert_equal, len(hist.buffer), 1
        yield assert_equal, 'ls foobazz', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls foo', 'rtn': 2})
        yield assert_equal, len(hist.buffer), 1
        yield assert_equal, 'ls foobazz', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # File now exists, success
        hist.append({'inp': 'ls foo', 'rtn': 0})
        yield assert_equal, len(hist.buffer), 2
        yield assert_equal, 'ls foo', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # Success
        hist.append({'inp': 'ls', 'rtn': 0})
        yield assert_equal, len(hist.buffer), 3
        yield assert_equal, 'ls', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # Dup
        hist.append({'inp': 'ls', 'rtn': 0})
        yield assert_equal, len(hist.buffer), 3

        # Success
        hist.append({'inp': '/bin/ls', 'rtn': 0})
        yield assert_equal, len(hist.buffer), 4
        yield assert_equal, '/bin/ls', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls bazz', 'rtn': 1})
        yield assert_equal, len(hist.buffer), 4
        yield assert_equal, '/bin/ls', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls bazz', 'rtn': -1})
        yield assert_equal, len(hist.buffer), 4
        yield assert_equal, '/bin/ls', hist.buffer[-1]['inp']
        yield assert_equal, 0, hist.buffer[-1]['rtn']

    os.remove(FNAME)


if __name__ == '__main__':
    nose.runmodule()
