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

from xonsh.lazyjson import LazyJSON
from xonsh.history import History
from xonsh import history

from tools import mock_xonsh_env

HIST_TEST_KWARGS = dict(sessionid='SESSIONID', gc=False)


def test_hist_init():
    """Test initialization of the shell history."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.init'
    History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with LazyJSON(FNAME) as lj:
        obs = lj['here']
    assert 'yup' == obs
    os.remove(FNAME)


def test_hist_append():
    """Verify appending to the history works."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.append'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hf = hist.append({'joco': 'still alive'})
    assert hf is None
    assert 'still alive' == hist.buffer[0]['joco']
    os.remove(FNAME)


def test_hist_flush():
    """Verify explicit flushing of the history works."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.flush'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    hf = hist.flush()
    assert hf is None
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hist.append({'joco': 'still alive'})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(FNAME) as lj:
        obs = lj['cmds'][0]['joco']
    assert 'still alive' == obs
    os.remove(FNAME)


def test_cmd_field():
    """Test basic history behavior."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.cmdfield'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    # in-memory
    with mock_xonsh_env({'HISTCONTROL': set()}):
        hf = hist.append({'rtn': 1})
    assert hf is None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert None == hist.outs[-1]
    # slice
    assert [1] == hist.rtns[:]
    # on disk
    hf = hist.flush()
    assert hf is not None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert None == hist.outs[-1]
    os.remove(FNAME)


def test_show_cmd():
    """Verify that CLI history commands work."""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.show_cmd'
    cmds = ['ls', 'cat hello kitty', 'abc', 'def', 'touch me', 'grep from me']

    def format_hist_line(idx, cmd):
        """Construct a history output line."""
        return ' {:d}: {:s}\n'.format(idx, cmd)

    def run_show_cmd(hist_args, commands, base_idx=0, step=1):
        """Run and evaluate the output of the given show command."""
        stdout.seek(0, io.SEEK_SET)
        stdout.truncate()
        history._hist_main(hist, hist_args)
        stdout.seek(0, io.SEEK_SET)
        hist_lines = stdout.readlines()
        assert len(commands) == len(hist_lines)
        for idx, (cmd, actual) in enumerate(zip(commands, hist_lines)):
            expected = format_hist_line(base_idx + idx * step, cmd)
            assert expected == actual

    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)
    stdout = io.StringIO()
    saved_stdout = sys.stdout
    sys.stdout = stdout

    with mock_xonsh_env({'HISTCONTROL': set()}):
        for ts,cmd in enumerate(cmds):  # populate the shell history
            hist.append({'inp': cmd, 'rtn': 0, 'ts':(ts+1, ts+1.5)})

        # Verify an implicit "show" emits show history
        run_show_cmd([], cmds)

        # Verify an explicit "show" with no qualifiers emits
        # show history.
        run_show_cmd(['show'], cmds)

        # Verify an explicit "show" with a reversed qualifier
        # emits show history in reverse order.
        run_show_cmd(['show', '-r'], list(reversed(cmds)),
                                 len(cmds) - 1, -1)

        # Verify that showing a specific history entry relative to
        # the start of the history works.
        run_show_cmd(['show', '0'], [cmds[0]], 0)
        run_show_cmd(['show', '1'], [cmds[1]], 1)

        # Verify that showing a specific history entry relative to
        # the end of the history works.
        run_show_cmd(['show', '-2'], [cmds[-2]],
                               len(cmds) - 2)

        # Verify that showing a history range relative to the start of the
        # history works.
        run_show_cmd(['show', '0:2'], cmds[0:2], 0)
        run_show_cmd(['show', '1::2'], cmds[1::2], 1, 2)

        # Verify that showing a history range relative to the end of the
        # history works.
        run_show_cmd(['show', '-2:'],
                               cmds[-2:], len(cmds) - 2)
        run_show_cmd(['show', '-4:-2'],
                               cmds[-4:-2], len(cmds) - 4)

    sys.stdout = saved_stdout
    os.remove(FNAME)

def test_histcontrol():
    """Test HISTCONTROL=ignoredups,ignoreerr"""
    FNAME = 'xonsh-SESSIONID.json'
    FNAME += '.append'
    hist = History(filename=FNAME, here='yup', **HIST_TEST_KWARGS)

    with mock_xonsh_env({'HISTCONTROL': 'ignoredups,ignoreerr'}):
        assert len(hist.buffer) == 0

        # An error, buffer remains empty
        hist.append({'inp': 'ls foo', 'rtn': 2})
        assert len(hist.buffer) == 0

        # Success
        hist.append({'inp': 'ls foobazz', 'rtn': 0})
        assert len(hist.buffer) == 1
        assert 'ls foobazz' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls foo', 'rtn': 2})
        assert len(hist.buffer) == 1
        assert 'ls foobazz' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # File now exists, success
        hist.append({'inp': 'ls foo', 'rtn': 0})
        assert len(hist.buffer) == 2
        assert 'ls foo' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # Success
        hist.append({'inp': 'ls', 'rtn': 0})
        assert len(hist.buffer) == 3
        assert 'ls' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # Dup
        hist.append({'inp': 'ls', 'rtn': 0})
        assert len(hist.buffer) == 3

        # Success
        hist.append({'inp': '/bin/ls', 'rtn': 0})
        assert len(hist.buffer) == 4
        assert '/bin/ls' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls bazz', 'rtn': 1})
        assert len(hist.buffer) == 4
        assert '/bin/ls' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

        # Error
        hist.append({'inp': 'ls bazz', 'rtn': -1})
        assert len(hist.buffer) == 4
        assert '/bin/ls' == hist.buffer[-1]['inp']
        assert 0 == hist.buffer[-1]['rtn']

    os.remove(FNAME)
