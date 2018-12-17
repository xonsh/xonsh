# -*- coding: utf-8 -*-
"""Tests the xonsh history."""
# pylint: disable=protected-access
import os
import shlex

from xonsh.history.sqlite import SqliteHistory
from xonsh.history.main import history_main

import pytest


@pytest.fixture
def hist():
    h = SqliteHistory(
        filename="xonsh-HISTORY-TEST.sqlite", sessionid="SESSIONID", gc=False
    )
    yield h
    os.remove(h.filename)


def test_hist_append(hist, xonsh_builtins):
    """Verify appending to the history works."""
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    hf = hist.append({"inp": "still alive", "rtn": 1})
    assert hf is None
    items = list(hist.items())
    assert len(items) == 1
    assert "still alive" == items[0]["inp"]
    assert 1 == items[0]["rtn"]
    hist.append({"inp": "still alive", "rtn": 0})
    items = list(hist.items())
    assert len(items) == 2
    assert "still alive" == items[1]["inp"]
    assert 0 == items[1]["rtn"]
    assert list(hist.all_items()) == items


def test_hist_attrs(hist, xonsh_builtins):
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    hf = hist.append({"inp": "ls foo", "rtn": 1})
    assert hf is None
    assert "ls foo" == hist.inps[0]
    assert "ls foo" == hist.inps[-1]
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert None is hist.outs[-1]
    assert [1] == hist.rtns[:]
    hist.append({"inp": "ls bar", "rtn": 0})
    assert "ls bar" == hist.inps[1]
    assert "ls bar" == hist.inps[-1]
    assert 0 == hist.rtns[1]
    assert 0 == hist.rtns[-1]
    assert None is hist.outs[-1]
    assert [1, 0] == hist.rtns[:]
    assert len(hist.tss) == 2
    assert len(hist.tss[0]) == 2


CMDS = ["ls", "cat hello kitty", "abc", "def", "touch me", "grep from me"]


@pytest.mark.parametrize(
    "inp, commands, offset",
    [
        ("", CMDS, (0, 1)),
        ("-r", list(reversed(CMDS)), (len(CMDS) - 1, -1)),
        ("0", CMDS[0:1], (0, 1)),
        ("1", CMDS[1:2], (1, 1)),
        ("-2", CMDS[-2:-1], (len(CMDS) - 2, 1)),
        ("1:3", CMDS[1:3], (1, 1)),
        ("1::2", CMDS[1::2], (1, 2)),
        ("-4:-2", CMDS[-4:-2], (len(CMDS) - 4, 1)),
    ],
)
def test_show_cmd_numerate(inp, commands, offset, hist, xonsh_builtins, capsys):
    """Verify that CLI history commands work."""
    base_idx, step = offset
    xonsh_builtins.__xonsh__.history = hist
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    for ts, cmd in enumerate(CMDS):  # populate the shell history
        hist.append({"inp": cmd, "rtn": 0, "ts": (ts + 1, ts + 1.5)})

    exp = (
        "{}: {}".format(base_idx + idx * step, cmd)
        for idx, cmd in enumerate(list(commands))
    )
    exp = "\n".join(exp)

    history_main(["show", "-n"] + shlex.split(inp))
    out, err = capsys.readouterr()
    assert out.rstrip() == exp


def test_histcontrol(hist, xonsh_builtins):
    """Test HISTCONTROL=ignoredups,ignoreerr"""

    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = "ignoredups,ignoreerr"
    assert len(hist) == 0

    # An error, items() remains empty
    hist.append({"inp": "ls foo", "rtn": 2})
    assert len(hist) == 0
    assert len(hist.inps) == 1
    assert len(hist.rtns) == 1
    assert 2 == hist.rtns[-1]

    # Success
    hist.append({"inp": "ls foobazz", "rtn": 0})
    assert len(hist) == 1
    assert len(hist.inps) == 2
    assert len(hist.rtns) == 2
    items = list(hist.items())
    assert "ls foobazz" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert 0 == hist.rtns[-1]

    # Error
    hist.append({"inp": "ls foo", "rtn": 2})
    assert len(hist) == 1
    items = list(hist.items())
    assert "ls foobazz" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert 2 == hist.rtns[-1]

    # File now exists, success
    hist.append({"inp": "ls foo", "rtn": 0})
    assert len(hist) == 2
    items = list(hist.items())
    assert "ls foo" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert 0 == hist.rtns[-1]

    # Success
    hist.append({"inp": "ls", "rtn": 0})
    assert len(hist) == 3
    items = list(hist.items())
    assert "ls" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert 0 == hist.rtns[-1]

    # Dup
    hist.append({"inp": "ls", "rtn": 0})
    assert len(hist) == 3

    # Success
    hist.append({"inp": "/bin/ls", "rtn": 0})
    assert len(hist) == 4
    items = list(hist.items())
    assert "/bin/ls" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert 0 == hist.rtns[-1]

    # Error
    hist.append({"inp": "ls bazz", "rtn": 1})
    assert len(hist) == 4
    items = list(hist.items())
    assert "/bin/ls" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert "ls bazz" == hist.inps[-1]
    assert 1 == hist.rtns[-1]

    # Error
    hist.append({"inp": "ls bazz", "rtn": -1})
    assert len(hist) == 4
    items = list(hist.items())
    assert "/bin/ls" == items[-1]["inp"]
    assert 0 == items[-1]["rtn"]
    assert -1 == hist.rtns[-1]


@pytest.mark.parametrize(
    "index, exp",
    [
        (-1, ("grep from me", "out", 0, (5, 6))),
        (1, ("cat hello kitty", "out", 0, (1, 2))),
        (
            slice(1, 3),
            [("cat hello kitty", "out", 0, (1, 2)), ("abc", "out", 0, (2, 3))],
        ),
    ],
)
def test_history_getitem(index, exp, hist, xonsh_builtins):
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    xonsh_builtins.__xonsh__.env["XONSH_STORE_STDOUT"] = True
    attrs = ("inp", "out", "rtn", "ts")

    for ts, cmd in enumerate(CMDS):  # populate the shell history
        entry = {k: v for k, v in zip(attrs, [cmd, "out", 0, (ts, ts + 1)])}
        hist.append(entry)

    entry = hist[index]
    if isinstance(entry, list):
        assert [(e.cmd, e.out, e.rtn, e.ts) for e in entry] == exp
    else:
        assert (entry.cmd, entry.out, entry.rtn, entry.ts) == exp
