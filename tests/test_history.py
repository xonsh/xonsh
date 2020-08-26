# -*- coding: utf-8 -*-
"""Tests the json history backend."""
# pylint: disable=protected-access
import os
import shlex

import pytest

from xonsh.lazyjson import LazyJSON
from xonsh.history.dummy import DummyHistory
from xonsh.history.json import (
    JsonHistory,
    _xhj_gc_commands_to_rmfiles,
    _xhj_gc_files_to_rmfiles,
    _xhj_gc_seconds_to_rmfiles,
    _xhj_gc_bytes_to_rmfiles,
)

from xonsh.history.main import history_main, _xh_parse_args, construct_history


CMDS = ["ls", "cat hello kitty", "abc", "def", "touch me", "grep from me"]


@pytest.fixture
def hist():
    h = JsonHistory(
        filename="xonsh-HISTORY-TEST.json", here="yup", sessionid="SESSIONID", gc=False
    )
    yield h
    os.remove(h.filename)


def test_hist_init(hist):
    """Test initialization of the shell history."""
    with LazyJSON(hist.filename) as lj:
        obs = lj["here"]
    assert "yup" == obs


def test_hist_append(hist, xonsh_builtins):
    """Verify appending to the history works."""
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    hf = hist.append({"inp": "still alive", "rtn": 0})
    assert hf is None
    assert "still alive" == hist.buffer[0]["inp"]
    assert 0 == hist.buffer[0]["rtn"]
    assert 0 == hist.rtns[-1]
    hf = hist.append({"inp": "dead now", "rtn": 1})
    assert "dead now" == hist.buffer[1]["inp"]
    assert 1 == hist.buffer[1]["rtn"]
    assert 1 == hist.rtns[-1]
    hf = hist.append({"inp": "reborn", "rtn": 0})
    assert "reborn" == hist.buffer[2]["inp"]
    assert 0 == hist.buffer[2]["rtn"]
    assert 0 == hist.rtns[-1]


def test_hist_flush(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    hist.append({"inp": "still alive?", "rtn": 0, "out": "yes"})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(hist.filename) as lj:
        assert len(lj["cmds"]) == 1
        cmd = lj["cmds"][0]
        assert cmd["inp"] == "still alive?"
        assert not cmd.get("out", None)


def test_hist_flush_with_store_stdout(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    xonsh_builtins.__xonsh__.env["XONSH_STORE_STDOUT"] = True
    hist.append({"inp": "still alive?", "rtn": 0, "out": "yes"})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    with LazyJSON(hist.filename) as lj:
        assert len(lj["cmds"]) == 1
        assert lj["cmds"][0]["inp"] == "still alive?"
        assert lj["cmds"][0]["out"].strip() == "yes"


def test_hist_flush_with_hist_control(hist, xonsh_builtins):
    """Verify explicit flushing of the history works."""
    hf = hist.flush()
    assert hf is None
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = "ignoredups,ignoreerr"
    hist.append({"inp": "ls foo1", "rtn": 0})
    hist.append({"inp": "ls foo1", "rtn": 1})
    hist.append({"inp": "ls foo1", "rtn": 0})
    hist.append({"inp": "ls foo2", "rtn": 2})
    hist.append({"inp": "ls foo3", "rtn": 0})
    hf = hist.flush()
    assert hf is not None
    while hf.is_alive():
        pass
    assert len(hist.buffer) == 0
    with LazyJSON(hist.filename) as lj:
        cmds = list(lj["cmds"])
        assert len(cmds) == 2
        assert [x["inp"] for x in cmds] == ["ls foo1", "ls foo3"]
        assert [x["rtn"] for x in cmds] == [0, 0]


def test_cmd_field(hist, xonsh_builtins):
    # in-memory
    xonsh_builtins.__xonsh__.env["HISTCONTROL"] = set()
    hf = hist.append({"inp": "ls foo", "rtn": 1})
    assert hf is None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert hist.outs[-1] is None
    # slice
    assert [1] == hist.rtns[:]
    # on disk
    hf = hist.flush()
    assert hf is not None
    assert 1 == hist.rtns[0]
    assert 1 == hist.rtns[-1]
    assert hist.outs[-1] is None


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
    assert len(hist.buffer) == 0

    # An error, buffer remains empty
    hist.append({"inp": "ls foo", "rtn": 2})
    assert len(hist.buffer) == 1
    assert hist.rtns[-1] == 2
    assert hist.inps[-1] == "ls foo"

    # Success
    hist.append({"inp": "ls foobazz", "rtn": 0})
    assert len(hist.buffer) == 2
    assert "ls foobazz" == hist.buffer[-1]["inp"]
    assert 0 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == "ls foobazz"

    # Error
    hist.append({"inp": "ls foo", "rtn": 2})
    assert len(hist.buffer) == 3
    assert "ls foo" == hist.buffer[-1]["inp"]
    assert 2 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 2
    assert hist.inps[-1] == "ls foo"

    # File now exists, success
    hist.append({"inp": "ls foo", "rtn": 0})
    assert len(hist.buffer) == 4
    assert "ls foo" == hist.buffer[-1]["inp"]
    assert 0 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == "ls foo"

    # Success
    hist.append({"inp": "ls", "rtn": 0})
    assert len(hist.buffer) == 5
    assert "ls" == hist.buffer[-1]["inp"]
    assert 0 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == "ls"

    # Dup
    hist.append({"inp": "ls", "rtn": 0})
    assert len(hist.buffer) == 6
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == "ls"

    # Success
    hist.append({"inp": "/bin/ls", "rtn": 0})
    assert len(hist.buffer) == 7
    assert "/bin/ls" == hist.buffer[-1]["inp"]
    assert 0 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 0
    assert hist.inps[-1] == "/bin/ls"

    # Error
    hist.append({"inp": "ls bazz", "rtn": 1})
    assert len(hist.buffer) == 8
    assert "ls bazz" == hist.buffer[-1]["inp"]
    assert 1 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == 1
    assert hist.inps[-1] == "ls bazz"

    # Error
    hist.append({"inp": "ls bazz", "rtn": -1})
    assert len(hist.buffer) == 9
    assert "ls bazz" == hist.buffer[-1]["inp"]
    assert -1 == hist.buffer[-1]["rtn"]
    assert hist.rtns[-1] == -1
    assert hist.inps[-1] == "ls bazz"


@pytest.mark.parametrize("args", ["-h", "--help", "show -h", "show --help"])
def test_parse_args_help(args, capsys):
    with pytest.raises(SystemExit):
        args = _xh_parse_args(shlex.split(args))
    assert "show this help message and exit" in capsys.readouterr()[0]


@pytest.mark.parametrize(
    "args, exp",
    [
        ("", ("show", "session", [], False, False)),
        ("1:5", ("show", "session", ["1:5"], False, False)),
        ("show", ("show", "session", [], False, False)),
        ("show 15", ("show", "session", ["15"], False, False)),
        ("show bash 3:5 15:66", ("show", "bash", ["3:5", "15:66"], False, False)),
        ("show -r", ("show", "session", [], False, True)),
        ("show -rn bash", ("show", "bash", [], True, True)),
        ("show -n -r -30:20", ("show", "session", ["-30:20"], True, True)),
        ("show -n zsh 1:2:3", ("show", "zsh", ["1:2:3"], True, False)),
    ],
)
def test_parser_show(args, exp):
    # use dict instead of argparse.Namespace for pretty pytest diff
    exp_ns = {
        "action": exp[0],
        "session": exp[1],
        "slices": exp[2],
        "numerate": exp[3],
        "reverse": exp[4],
        "start_time": None,
        "end_time": None,
        "datetime_format": None,
        "timestamp": False,
        "null_byte": False,
    }
    ns = _xh_parse_args(shlex.split(args))
    assert ns.__dict__ == exp_ns


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
    attrs = ("inp", "out", "rtn", "ts")

    for ts, cmd in enumerate(CMDS):  # populate the shell history
        entry = {k: v for k, v in zip(attrs, [cmd, "out", 0, (ts, ts + 1)])}
        hist.append(entry)

    entry = hist[index]
    if isinstance(entry, list):
        assert [(e.cmd, e.out, e.rtn, e.ts) for e in entry] == exp
    else:
        assert (entry.cmd, entry.out, entry.rtn, entry.ts) == exp


def test_construct_history_str(xonsh_builtins):
    xonsh_builtins.__xonsh__.env["XONSH_HISTORY_BACKEND"] = "dummy"
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_class(xonsh_builtins):
    xonsh_builtins.__xonsh__.env["XONSH_HISTORY_BACKEND"] = DummyHistory
    assert isinstance(construct_history(), DummyHistory)


def test_construct_history_instance(xonsh_builtins):
    xonsh_builtins.__xonsh__.env["XONSH_HISTORY_BACKEND"] = DummyHistory()
    assert isinstance(construct_history(), DummyHistory)


import time
import calendar


HF_FIRST_DAY = calendar.timegm(time.struct_time((2018, 5, 13, 0, 0, 0, 0, 0, 0)))


def history_files_list(gen_count) -> (float, int, str, int):
    """Generate a list of history file tuples"""
    # generate test list:
    # 2 files every day in range
    # morning file has 100 commands, evening 50
    # first file size 10000, 2nd 2500
    # first file time 0900, 2nd 2300
    # for sanity in reproducable test results, all date arithmetic ignores astronomy.
    # time zone is UTC, all days have 24 h and 0 sec, no leap year or leap sec.

    retval = []
    for i in range(int((gen_count + 1) / 2)):
        retval.append(
            (
                # first day in sec + #days * 24hr + #hr * 60min + # sec * 60sec + sec= sec to date.
                HF_FIRST_DAY + (((((i * 24) + 9) * 60) + 0) * 60) + 0,  # mod dt,
                100,
                f".argle/xonsh-{2*i:05n}.json",
                10000,
            )
        )
        retval.append(
            (
                # first day in sec + #days * 24hr + #hr * 60min + # sec * 60sec + sec= sec to date.
                HF_FIRST_DAY + (((((i * 24) + 23) * 60) + 0) * 60) + 0,  # mod dt,
                50,
                f".argle/xonsh-{2*i+1:05n}.json",
                2500,
            )
        )
    return retval


# generate 100 files, 50 days.
HISTORY_FILES_LIST = history_files_list(100)

# TS of newest history file
SEC_FROM_LATEST = time.time() - (HISTORY_FILES_LIST[-1][0])
SEC_FROM_OLDEST = time.time() - (HISTORY_FILES_LIST[0][0])
SEC_PER_DAY = 24 * 60 * 60
SEC_PER_HR = 60 * 60


@pytest.mark.parametrize(
    "fn, hsize, in_files, exp_size, exp_files",
    [
        # xhj_gc_commands_to_rmfiles
        (
            _xhj_gc_commands_to_rmfiles,
            1001 * (100 + 50),  # Limit > history, no trimming.
            HISTORY_FILES_LIST,
            0,  # nothing trimmed
            [],  #
        ),
        (
            _xhj_gc_commands_to_rmfiles,
            20 * (100 + 50),  # keep 20 full days (40 files)
            HISTORY_FILES_LIST,
            30 * (100 + 50),
            HISTORY_FILES_LIST[: 2 * (30)],  # trim 30 full days
        ),
        (
            _xhj_gc_commands_to_rmfiles,
            20 * (100 + 50) + 100,  # keep 20 full newest and evening before (41 files)
            HISTORY_FILES_LIST,
            30 * (100 + 50) - 50,  # trim 30 full oldest, keep newest evening (59 files)
            HISTORY_FILES_LIST[: 2 * 30 - 1],
        ),
        # xhj_gc_files_to_rmfiles
        (
            _xhj_gc_files_to_rmfiles,
            1001,  # Limit > history, no trimming.
            HISTORY_FILES_LIST,
            0,  # nothing trimmed
            [],  #
        ),
        (
            _xhj_gc_files_to_rmfiles,
            40,  # keep 20 full days (40 files)
            HISTORY_FILES_LIST,
            60,
            HISTORY_FILES_LIST[:60],  # trim 30 full days
        ),
        (
            _xhj_gc_files_to_rmfiles,
            41,  # keep 20 full newest and evening before (41 files)
            HISTORY_FILES_LIST,
            59,  # trim 30 full oldest, keep newest evening (59 files)
            HISTORY_FILES_LIST[: 2 * 30 - 1],
        ),
        # xhj_gc_bytes_to_rmfiles
        (
            _xhj_gc_bytes_to_rmfiles,
            1001 * (10000 + 2500),  # Limit > history, no trimming.
            HISTORY_FILES_LIST,
            0,  # nothing trimmed
            [],  #
        ),
        (
            _xhj_gc_bytes_to_rmfiles,
            20 * (10000 + 2500),  # keep 20 full days (40 files)
            HISTORY_FILES_LIST,
            30 * (10000 + 2500),
            HISTORY_FILES_LIST[: 2 * (30)],  # trim 30 full days
        ),
        (
            _xhj_gc_bytes_to_rmfiles,
            20 * (10000 + 2500)
            + 10000,  # keep 20 full newest and evening before (41 files)
            HISTORY_FILES_LIST,
            30 * (10000 + 2500)
            - 2500,  # trim 30 full oldest, keep newest evening (59 files)
            HISTORY_FILES_LIST[: 2 * 30 - 1],
        ),
        # xhj_gc_seconds_to_rmfiles
        # amount of history removed by age is strange.
        # it's always the age of the *oldest* file, no matter how many would be removed.
        (
            _xhj_gc_seconds_to_rmfiles,
            SEC_FROM_LATEST + 1001 * SEC_PER_DAY,  # Limit > history, no trimming.
            HISTORY_FILES_LIST,
            0,  # nothing trimmed
            [],  #
        ),
        (
            _xhj_gc_seconds_to_rmfiles,
            SEC_FROM_LATEST + 20 * SEC_PER_DAY,  # keep 20 full days (40 files)
            HISTORY_FILES_LIST,
            SEC_FROM_OLDEST,
            HISTORY_FILES_LIST[: 2 * (30)],  # trim 30 full days
        ),
        (
            _xhj_gc_seconds_to_rmfiles,
            SEC_FROM_LATEST
            + 20 * SEC_PER_DAY
            + 1 * SEC_PER_HR,  # keep 20 full newest and evening before (41 files)
            HISTORY_FILES_LIST,
            SEC_FROM_OLDEST,
            HISTORY_FILES_LIST[: 2 * 30 - 1],
        ),
    ],
)
def test__xhj_gc_xx_to_rmfiles(
    fn, hsize, in_files, exp_size, exp_files, xonsh_builtins
):

    act_size, act_files = fn(hsize, in_files)

    assert act_files == exp_files

    # comparing age is approximate, because xhj_gc_seconds_to_rmfiles computes 'now' on each call.
    # For test runs, accept anything in the same hour, test cases not that close.
    # We find multi-minute variations in CI environments.
    # This should cover some amount of think time sitting at a breakpoint, too.
    if fn == _xhj_gc_seconds_to_rmfiles:
        minute_diff = int(abs(act_size - exp_size) / 60)
        assert minute_diff <= 60
    else:
        assert act_size == exp_size
