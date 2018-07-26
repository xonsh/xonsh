# -*- coding: utf-8 -*-
"""Tests the json history backend."""
# pylint: disable=protected-access
import os
import shlex

import pytest

from xonsh.lazyjson import LazyJSON
from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory
from xonsh.history.main import history_main, _xh_parse_args, construct_history


CMDS = ['ls', 'cat hello kitty', 'abc', 'def', 'touch me', 'grep from me']

@pytest.yield_fixture
def hist():
    h = JsonHistory(filename='xonsh-HISTORY-TEST.json', here='yup',
                    sessionid='SESSIONID', gc=False)
    yield h
    os.remove(h.filename)


def test_hist_init(hist):
    """Test initialization of the shell history."""
    with LazyJSON(hist.filename) as lj:
        obs = lj['here']
    assert 'yup' == obs


def test_hist_append(hist, xonsh_builtins):
    """Verify appending to the history works."""
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hf = hist.append({'inp': 'still alive', 'rtn': 0})
    assert hf is None
    assert 'still alive' == hist.buffer[0]['inp']
    assert 0 == hist.buffer[0]['rtn']
    assert 0 == hist.rtns[-1]
    hf = hist.append({'inp': 'dead now', 'rtn': 1})
    assert 'dead now' == hist.buffer[1]['inp']
    assert 1 == hist.buffer[1]['rtn']
    assert 1 == hist.rtns[-1]
    hf = hist.append({'inp': 'reborn', 'rtn': 0})
    assert 'reborn' == hist.buffer[2]['inp']
    assert 0 == hist.buffer[2]['rtn']
    assert 0 == hist.rtns[-1]


def test_hist_flush(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hist.append({'inp': 'still alive?', 'rtn': 0, 'out': 'yes'})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(hist.filename) as lj:
        assert len(lj['cmds']) == 1
        cmd = lj['cmds'][0]
        assert cmd['inp'] == 'still alive?'
        assert not cmd.get('out', None)


def test_hist_flush_with_store_stdout(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    xonsh_builtins.__xonsh_env__['XONSH_STORE_STDOUT'] = True
    hist.append({'inp': 'still alive?', 'rtn': 0, 'out': 'yes'})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(hist.filename) as lj:
        assert len(lj['cmds']) == 1
        assert lj['cmds'][0]['inp'] == 'still alive?'
        assert lj['cmds'][0]['out'].strip() == 'yes'


def test_hist_flush_with_hist_control(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = 'ignoredups,ignoreerr'
    hist.append({'inp': 'ls foo1', 'rtn': 0})
    hist.append({'inp': 'ls foo1', 'rtn': 1})
    hist.append({'inp': 'ls foo1', 'rtn': 0})
    hist.append({'inp': 'ls foo2', 'rtn': 2})
    hist.append({'inp': 'ls foo3', 'rtn': 0})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    assert len(hist.buffer) == 0
    with LazyJSON(hist.filename) as lj:
        cmds = list(lj['cmds'])
        assert len(cmds) == 2
        assert [x['inp'] for x in cmds] == ['ls foo1', 'ls foo3']
        assert [x['rtn'] for x in cmds] == [0, 0]


def test_cmd_field(hist, xonsh_builtins):
    # in-memory
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    hf = hist.append({'inp': 'ls foo', 'rtn': 1})
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


@pytest.mark.parametrize('inp, commands, offset', [
    ('', CMDS, (0, 1)),
    ('-r', list(reversed(CMDS)), (len(CMDS)- 1, -1)),
    ('0', CMDS[0:1], (0, 1)),
    ('1', CMDS[1:2], (1, 1)),
    ('-2', CMDS[-2:-1], (len(CMDS) -2 , 1)),
    ('1:3', CMDS[1:3], (1, 1)),
    ('1::2', CMDS[1::2], (1, 2)),
    ('-4:-2', CMDS[-4:-2], (len(CMDS) - 4, 1))
    ])
def test_show_cmd_numerate(inp, commands, offset, hist, xonsh_builtins, capsys):
    """Verify that CLI history commands work."""
    base_idx, step = offset
    xonsh_builtins.__xonsh_history__ = hist
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    for ts, cmd in enumerate(CMDS):  # populate the shell history
        hist.append({'inp': cmd, 'rtn': 0, 'ts':(ts + 1, ts + 1.5)})

    exp = ('{}: {}'.format(base_idx + idx * step, cmd)
           for idx, cmd in enumerate(list(commands)))
    exp = '\n'.join(exp)

    history_main(['show', '-n'] + shlex.split(inp))
    out, err = capsys.readouterr()
    assert out.rstrip() == exp


def test_histcontrol(hist, xonsh_builtins):
    """Test HISTCONTROL=ignoredups,ignoreerr"""

    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = 'ignoredups,ignoreerr'
    assert len(hist.buffer) == 0

    # An error, buffer remains empty
    hist.append({'inp': 'ls foo', 'rtn': 2})
    assert len(hist.buffer) == 1
    assert hist.rtns[-1] == 2
    assert hist.inps[-1] == 'ls foo'

    # Success
    hist.append({'inp': 'ls foobazz', 'rtn': 0})
    assert len(hist.buffer) == 2
    assert 'ls foobazz' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == 'ls foobazz'

    # Error
    hist.append({'inp': 'ls foo', 'rtn': 2})
    assert len(hist.buffer) == 3
    assert 'ls foo' == hist.buffer[-1]['inp']
    assert 2 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 2
    assert hist.inps[-1] == 'ls foo'

    # File now exists, success
    hist.append({'inp': 'ls foo', 'rtn': 0})
    assert len(hist.buffer) == 4
    assert 'ls foo' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == 'ls foo'

    # Success
    hist.append({'inp': 'ls', 'rtn': 0})
    assert len(hist.buffer) == 5
    assert 'ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == 'ls'

    # Dup
    hist.append({'inp': 'ls', 'rtn': 0})
    assert len(hist.buffer) == 6
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == 'ls'

    # Success
    hist.append({'inp': '/bin/ls', 'rtn': 0})
    assert len(hist.buffer) == 7
    assert '/bin/ls' == hist.buffer[-1]['inp']
    assert 0 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == '/bin/ls'

    # Error
    hist.append({'inp': 'ls bazz', 'rtn': 1})
    assert len(hist.buffer) == 8
    assert 'ls bazz' == hist.buffer[-1]['inp']
    assert 1 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == 1
    assert hist.inps[-1] == 'ls bazz'

    # Error
    hist.append({'inp': 'ls bazz', 'rtn': -1})
    assert len(hist.buffer) == 9
    assert 'ls bazz' == hist.buffer[-1]['inp']
    assert -1 == hist.buffer[-1]['rtn']
    assert hist.rtns[-1] == -1
    assert hist.inps[-1] == 'ls bazz'


@pytest.mark.parametrize('args', [ '-h', '--help', 'show -h', 'show --help'])
def test_parse_args_help(args, capsys):
    with pytest.raises(SystemExit):
        args = _xh_parse_args(shlex.split(args))
    assert 'show this help message and exit' in capsys.readouterr()[0]


@pytest.mark.parametrize('args, exp', [
    ('', ('show', 'session', [], False, False)),
    ('1:5', ('show', 'session', ['1:5'], False, False)),
    ('show', ('show', 'session', [], False, False)),
    ('show 15', ('show', 'session', ['15'], False, False)),
    ('show bash 3:5 15:66', ('show', 'bash', ['3:5', '15:66'], False, False)),
    ('show -r', ('show', 'session', [], False, True)),
    ('show -rn bash', ('show', 'bash', [], True, True)),
    ('show -n -r -30:20', ('show', 'session', ['-30:20'], True, True)),
    ('show -n zsh 1:2:3', ('show', 'zsh', ['1:2:3'], True, False))
    ])
def test_parser_show(args, exp):
    # use dict instead of argparse.Namespace for pretty pytest diff
    exp_ns = {'action': exp[0],
              'session': exp[1],
              'slices': exp[2],
              'numerate': exp[3],
              'reverse': exp[4],
              'start_time': None,
              'end_time': None,
              'datetime_format': None,
              'timestamp': False,
              'null_byte': False}
    ns = _xh_parse_args(shlex.split(args))
    assert ns.__dict__ == exp_ns


@pytest.mark.parametrize('index, exp', [
    (-1, ('grep from me', 'out', 0, (5, 6))),
    (1, ('cat hello kitty', 'out', 0, (1, 2))),
    (slice(1, 3), [('cat hello kitty', 'out', 0, (1, 2)),
                   ('abc', 'out', 0, (2, 3))]),
])
def test_history_getitem(index, exp, hist, xonsh_builtins):
    xonsh_builtins.__xonsh_env__['HISTCONTROL'] = set()
    attrs = ('inp', 'out', 'rtn', 'ts')

    for ts,cmd in enumerate(CMDS):  # populate the shell history
        entry = {k: v for k, v in zip(attrs, [cmd, 'out', 0, (ts, ts+1)])}
        hist.append(entry)

    entry = hist[index]
    if isinstance(entry, list):
        assert [(e.cmd, e.out, e.rtn, e.ts) for e in entry] == exp
    else:
        assert (entry.cmd, entry.out, entry.rtn, entry.ts) == exp


def test_construct_history_str(xonsh_builtins):
    xonsh_builtins.__xonsh_env__['XONSH_HISTORY_BACKEND'] = 'dummy'
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_class(xonsh_builtins):
    xonsh_builtins.__xonsh_env__['XONSH_HISTORY_BACKEND'] = DummyHistory
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_instance(xonsh_builtins):
    xonsh_builtins.__xonsh_env__['XONSH_HISTORY_BACKEND'] = DummyHistory()
    assert isinstance(construct_history(), DummyHistory)
