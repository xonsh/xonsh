# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os
import tempfile
import builtins
import itertools
from tempfile import TemporaryDirectory
from xonsh.tools import ON_WINDOWS, always_true

import pytest

from xonsh.commands_cache import CommandsCache
from xonsh.environ import (
    Env,
    Ensurer,
    locate_binary,
    DEFAULT_ENSURERS,
    DEFAULT_VALUES,
    default_env,
    make_args_env,
    LsColors,
)

from tools import skip_if_on_unix


def test_env_normal():
    env = Env(VAR="wakka")
    assert "wakka" == env["VAR"]


def test_env_contains():
    env = Env(VAR="wakka")
    assert "VAR" in env


@pytest.mark.parametrize("path", [["/home/wakka"], ["wakka"]])
def test_env_path_list(path):
    env = Env(MYPATH=path)
    assert path == env["MYPATH"].paths


@pytest.mark.parametrize(
    "path",
    [["/home/wakka" + os.pathsep + "/home/jawaka"], ["wakka" + os.pathsep + "jawaka"]],
)
def test_env_path_str(path):
    env = Env(MYPATH=path)
    assert path == env["MYPATH"].paths


def test_env_detype():
    env = Env(MYPATH=["wakka", "jawaka"])
    assert "wakka" + os.pathsep + "jawaka" == env.detype()["MYPATH"]


@pytest.mark.parametrize(
    "path1, path2",
    [(["/home/wakka", "/home/jawaka"], "/home/woah"), (["wakka", "jawaka"], "woah")],
)
def test_env_detype_mutable_access_clear(path1, path2):
    env = Env(MYPATH=path1)
    assert path1[0] + os.pathsep + path1[1] == env.detype()["MYPATH"]
    env["MYPATH"][0] = path2
    assert env._detyped is None
    assert path2 + os.pathsep + path1[1] == env.detype()["MYPATH"]


def test_env_detype_no_dict():
    env = Env(YO={"hey": 42})
    env.set_ensurer("YO", Ensurer(always_true, None, None))
    det = env.detype()
    assert "YO" not in det


def test_histcontrol_none():
    env = Env(HISTCONTROL=None)
    assert isinstance(env["HISTCONTROL"], set)
    assert len(env["HISTCONTROL"]) == 0


def test_HISTCONTROL_empty():
    env = Env(HISTCONTROL="")
    assert isinstance(env["HISTCONTROL"], set)
    assert len(env["HISTCONTROL"]) == 0


def test_histcontrol_ignoredups():
    env = Env(HISTCONTROL="ignoredups")
    assert isinstance(env["HISTCONTROL"], set)
    assert len(env["HISTCONTROL"]) == 1
    assert "ignoredups" in env["HISTCONTROL"]
    assert "ignoreerr" not in env["HISTCONTROL"]


def test_histcontrol_ignoreerr_ignoredups():
    env = Env(HISTCONTROL="ignoreerr,ignoredups,ignoreerr")
    assert len(env["HISTCONTROL"]) == 2
    assert "ignoreerr" in env["HISTCONTROL"]
    assert "ignoredups" in env["HISTCONTROL"]


def test_swap():
    env = Env(VAR="wakka")
    assert env["VAR"] == "wakka"

    # positional arg
    with env.swap({"VAR": "foo"}):
        assert env["VAR"] == "foo"

    # make sure the environment goes back outside the context manager
    assert env["VAR"] == "wakka"

    # kwargs only
    with env.swap(VAR1="foo", VAR2="bar"):
        assert env["VAR1"] == "foo"
        assert env["VAR2"] == "bar"

    # positional and kwargs
    with env.swap({"VAR3": "baz"}, VAR1="foo", VAR2="bar"):
        assert env["VAR1"] == "foo"
        assert env["VAR2"] == "bar"
        assert env["VAR3"] == "baz"

    # make sure the environment goes back outside the context manager
    assert env["VAR"] == "wakka"
    assert "VAR1" not in env
    assert "VAR2" not in env
    assert "VAR3" not in env


def test_swap_exception_replacement():
    env = Env(VAR="original value")
    try:
        with env.swap(VAR="inner value"):
            assert env["VAR"] == "inner value"
            raise Exception()
    except Exception:
        assert env["VAR"] == "original value"
    assert env["VAR"] == "original value"


@skip_if_on_unix
def test_locate_binary_on_windows(xonsh_builtins):
    files = ("file1.exe", "FILE2.BAT", "file3.txt")
    with TemporaryDirectory() as tmpdir:
        for fname in files:
            fpath = os.path.join(tmpdir, fname)
            with open(fpath, "w") as f:
                f.write(fpath)
        xonsh_builtins.__xonsh__.env.update(
            {"PATH": [tmpdir], "PATHEXT": [".COM", ".EXE", ".BAT"]}
        )
        xonsh_builtins.__xonsh__.commands_cache = CommandsCache()
        assert locate_binary("file1") == os.path.join(tmpdir, "file1.exe")
        assert locate_binary("file1.exe") == os.path.join(tmpdir, "file1.exe")
        assert locate_binary("file2") == os.path.join(tmpdir, "FILE2.BAT")
        assert locate_binary("file2.bat") == os.path.join(tmpdir, "FILE2.BAT")
        assert locate_binary("file3") is None


def test_event_on_envvar_change(xonsh_builtins):
    env = Env(TEST=0)
    xonsh_builtins.__xonsh__.env = env
    share = []
    # register
    @xonsh_builtins.events.on_envvar_change
    def handler(name, oldvalue, newvalue, **kwargs):
        share.extend((name, oldvalue, newvalue))

    # trigger
    env["TEST"] = 1

    assert share == ["TEST", 0, 1]


def test_event_on_envvar_new(xonsh_builtins):
    env = Env()
    xonsh_builtins.__xonsh__.env = env
    share = []
    # register
    @xonsh_builtins.events.on_envvar_new
    def handler(name, value, **kwargs):
        share.extend((name, value))

    # trigger
    env["TEST"] = 1

    assert share == ["TEST", 1]


def test_event_on_envvar_change_from_none_value(xonsh_builtins):
    env = Env(TEST=None)
    xonsh_builtins.__xonsh__.env = env
    share = []
    # register
    @xonsh_builtins.events.on_envvar_change
    def handler(name, oldvalue, newvalue, **kwargs):
        share.extend((name, oldvalue, newvalue))

    # trigger
    env["TEST"] = 1

    assert share == ["TEST", None, 1]


@pytest.mark.parametrize("val", [1, None, True, "ok"])
def test_event_on_envvar_change_no_fire_when_value_is_same(val, xonsh_builtins):
    env = Env(TEST=val)
    xonsh_builtins.__xonsh__.env = env
    share = []
    # register
    @xonsh_builtins.events.on_envvar_change
    def handler(name, oldvalue, newvalue, **kwargs):
        share.extend((name, oldvalue, newvalue))

    # trigger
    env["TEST"] = val

    assert share == []


def test_events_on_envvar_called_in_right_order(xonsh_builtins):
    env = Env()
    xonsh_builtins.__xonsh__.env = env
    share = []
    # register
    @xonsh_builtins.events.on_envvar_new
    def handler(name, value, **kwargs):
        share[:] = ["new"]

    @xonsh_builtins.events.on_envvar_change
    def handler1(name, oldvalue, newvalue, **kwargs):
        share[:] = ["change"]

    # trigger new
    env["TEST"] = 1

    assert share == ["new"]

    # trigger change
    env["TEST"] = 2

    assert share == ["change"]


def test_int_bool_envvars_have_ensurers():
    bool_ints = [type(envvar) in [bool, int] for envvar in DEFAULT_VALUES.values()]
    key_mask = set(itertools.compress(DEFAULT_VALUES.keys(), bool_ints))
    ensurer_keys = set(DEFAULT_ENSURERS.keys())
    assert len(key_mask.intersection(ensurer_keys)) == len(key_mask)


def test_no_lines_columns():
    os.environ["LINES"] = "spam"
    os.environ["COLUMNS"] = "eggs"
    try:
        env = default_env()
        assert "LINES" not in env
        assert "COLUMNS" not in env
    finally:
        del os.environ["LINES"]
        del os.environ["COLUMNS"]


def test_make_args_env():
    obs = make_args_env(["script", "1", "2", "3"])
    exp = {
        "ARGS": ["script", "1", "2", "3"],
        "ARG0": "script",
        "ARG1": "1",
        "ARG2": "2",
        "ARG3": "3",
    }
    assert exp == obs


def test_delitem():
    env = Env(VAR="a value")
    assert env["VAR"] == "a value"
    del env["VAR"]
    with pytest.raises(Exception):
        a = env["VAR"]


def test_delitem_default():
    env = Env()
    a_key, a_value = next(
        (k, v) for (k, v) in env._defaults.items() if isinstance(v, str)
    )
    del env[a_key]
    assert env[a_key] == a_value
    del env[a_key]
    assert env[a_key] == a_value


def test_lscolors_target():
    lsc = LsColors.fromstring("ln=target")
    assert lsc["ln"] == ("TARGET",)
    assert lsc.detype() == "ln=target"


@pytest.mark.parametrize(
    "key_in,old_in,new_in,test",
    [
        ("rs", ("NO_COLOR",), ("BLUE",), "existing key, change value"),
        ("rs", ("NO_COLOR",), ("NO_COLOR",), "existing key, no change in value"),
        ("tw", None, ("NO_COLOR",), "create new key"),
        ("pi", ("BACKGROUND_BLACK", "YELLOW"), None, "delete existing key"),
    ],
)
def test_lscolors_events(key_in, old_in, new_in, test, xonsh_builtins):
    lsc = LsColors.fromstring("rs=0:di=01;34:pi=40;33")
    # corresponding colors: [('NO_COLOR',), ('BOLD_CYAN',), ('BOLD_CYAN',), ('BACKGROUND_BLACK', 'YELLOW')]

    event_fired = False

    @xonsh_builtins.events.on_lscolors_change
    def handler(key, oldvalue, newvalue, **kwargs):
        nonlocal old_in, new_in, key_in, event_fired
        assert (
            key == key_in and oldvalue == old_in and newvalue == new_in
        ), "Old and new event values match"
        event_fired = True

    xonsh_builtins.__xonsh__.env["LS_COLORS"] = lsc

    if new_in is None:
        old = lsc.pop(key_in, "argle")
    else:
        lsc[key_in] = new_in

    if old_in == new_in:
        assert not event_fired, "No event if value doesn't change"
    else:
        assert event_fired
