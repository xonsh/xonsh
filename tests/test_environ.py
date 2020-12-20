# -*- coding: utf-8 -*-
"""Tests the xonsh environment."""
from __future__ import unicode_literals, print_function
import os
import re
import pathlib
import datetime
import itertools
from tempfile import TemporaryDirectory

import pytest

from xonsh.tools import always_true, DefaultNotGiven
from xonsh.commands_cache import CommandsCache
from xonsh.environ import (
    Env,
    locate_binary,
    default_env,
    make_args_env,
    LsColors,
    default_value,
    Var,
)

from tools import skip_if_on_unix


def test_env_normal():
    env = Env(VAR="wakka")
    assert "wakka" == env["VAR"]


def test_env_contains():
    env = Env(VAR="wakka")
    assert "VAR" in env


@pytest.mark.parametrize("path", [["/home/wakka"], ["wakka"]])
def test_env_path_dirs_list(path):
    env = Env(MYPATH=path, MYDIRS=path)
    assert path == env["MYPATH"].paths
    assert path == env["MYDIRS"].paths


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
    env.register("YO", validate=always_true, convert=None, detype=None)
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


def test_histcontrol_ignoreerr_ignoredups_erase_dups():
    env = Env(HISTCONTROL="ignoreerr,ignoredups,ignoreerr,erasedups")
    assert len(env["HISTCONTROL"]) == 3
    assert "ignoreerr" in env["HISTCONTROL"]
    assert "ignoredups" in env["HISTCONTROL"]
    assert "erasedups" in env["HISTCONTROL"]


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
        tmpdir = os.path.realpath(tmpdir)
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
        env["VAR"]


def test_delitem_default():
    env = Env()
    a_key, a_value = next(
        (k, v.default) for (k, v) in env._vars.items() if isinstance(v.default, str)
    )
    del env[a_key]
    assert env[a_key] == a_value
    del env[a_key]
    assert env[a_key] == a_value


def test_lscolors_target(xonsh_builtins):
    lsc = LsColors.fromstring("ln=target")
    assert lsc["ln"] == ("RESET",)
    assert lsc.is_target("ln")
    assert lsc.detype() == "ln=target"
    assert not (lsc.is_target("mi"))


@pytest.mark.parametrize(
    "key_in,old_in,new_in,test",
    [
        ("fi", ("RESET",), ("BLUE",), "existing key, change value"),
        ("fi", ("RESET",), ("RESET",), "existing key, no change in value"),
        ("tw", None, ("RESET",), "create new key"),
        ("pi", ("BACKGROUND_BLACK", "YELLOW"), None, "delete existing key"),
    ],
)
def test_lscolors_events(key_in, old_in, new_in, test, xonsh_builtins):
    lsc = LsColors.fromstring("fi=0:di=01;34:pi=40;33")
    # corresponding colors: [('RESET',), ('BOLD_CYAN',), ('BOLD_CYAN',), ('BACKGROUND_BLACK', 'YELLOW')]

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
        lsc.pop(key_in, "argle")
    else:
        lsc[key_in] = new_in

    if old_in == new_in:
        assert not event_fired, "No event if value doesn't change"
    else:
        assert event_fired


def test_register_custom_var_generic():
    """Test that a registered envvar without any type is treated
    permissively.

    """
    env = Env()

    assert "MY_SPECIAL_VAR" not in env
    env.register("MY_SPECIAL_VAR")
    assert "MY_SPECIAL_VAR" in env

    env["MY_SPECIAL_VAR"] = 32
    assert env["MY_SPECIAL_VAR"] == 32

    env["MY_SPECIAL_VAR"] = True
    assert env["MY_SPECIAL_VAR"] is True


def test_register_custom_var_int():
    env = Env()
    env.register("MY_SPECIAL_VAR", type="int")

    env["MY_SPECIAL_VAR"] = "32"
    assert env["MY_SPECIAL_VAR"] == 32

    with pytest.raises(ValueError):
        env["MY_SPECIAL_VAR"] = "wakka"


def test_register_custom_var_float():
    env = Env()
    env.register("MY_SPECIAL_VAR", type="float")

    env["MY_SPECIAL_VAR"] = "27"
    assert env["MY_SPECIAL_VAR"] == 27.0

    with pytest.raises(ValueError):
        env["MY_SPECIAL_VAR"] = "wakka"


@pytest.mark.parametrize(
    "val,converted",
    [
        (True, True),
        (32, True),
        (0, False),
        (27.0, True),
        (None, False),
        ("lol", True),
        ("false", False),
        ("no", False),
    ],
)
def test_register_custom_var_bool(val, converted):
    env = Env()
    env.register("MY_SPECIAL_VAR", type="bool")

    env["MY_SPECIAL_VAR"] = val
    assert env["MY_SPECIAL_VAR"] == converted


@pytest.mark.parametrize(
    "val,converted",
    [
        (32, "32"),
        (0, "0"),
        (27.0, "27.0"),
        (None, "None"),
        ("lol", "lol"),
        ("false", "false"),
        ("no", "no"),
    ],
)
def test_register_custom_var_str(val, converted):
    env = Env()
    env.register("MY_SPECIAL_VAR", type="str")

    env["MY_SPECIAL_VAR"] = val
    assert env["MY_SPECIAL_VAR"] == converted


def test_register_var_path():
    env = Env()
    env.register("MY_PATH_VAR", type="path")

    path = "/tmp"
    env["MY_PATH_VAR"] = path
    assert env["MY_PATH_VAR"] == pathlib.Path(path)

    # Empty string is None to avoid uncontrolled converting empty string to Path('.')
    path = ""
    env["MY_PATH_VAR"] = path
    assert env["MY_PATH_VAR"] == None

    with pytest.raises(TypeError):
        env["MY_PATH_VAR"] = 42


def test_register_custom_var_env_path():
    env = Env()
    env.register("MY_SPECIAL_VAR", type="env_path")

    paths = ["/home/wakka", "/home/wakka/bin"]
    env["MY_SPECIAL_VAR"] = paths

    assert hasattr(env["MY_SPECIAL_VAR"], "paths")
    assert env["MY_SPECIAL_VAR"].paths == paths

    with pytest.raises(TypeError):
        env["MY_SPECIAL_VAR"] = 32


def test_deregister_custom_var():
    env = Env()

    env.register("MY_SPECIAL_VAR", type="env_path")
    env.deregister("MY_SPECIAL_VAR")
    assert "MY_SPECIAL_VAR" not in env

    env.register("MY_SPECIAL_VAR", type="env_path")
    paths = ["/home/wakka", "/home/wakka/bin"]
    env["MY_SPECIAL_VAR"] = paths
    env.deregister("MY_SPECIAL_VAR")

    # deregistering a variable that has a value set doesn't
    # remove it from env;
    # the existing variable also maintains its type validation, conversion
    assert "MY_SPECIAL_VAR" in env
    with pytest.raises(TypeError):
        env["MY_SPECIAL_VAR"] = 32

    # removing, then re-adding the variable without registering
    # gives it only default permissive validation, conversion
    del env["MY_SPECIAL_VAR"]
    env["MY_SPECIAL_VAR"] = 32


def test_register_callable_default():
    def is_date(x):
        return isinstance(x, datetime.date)

    @default_value
    def today(env):
        return datetime.date.today()

    # registration should not raise a value error just because
    # default is a function which generates the proper type.
    env = Env()
    env.register("TODAY", default=today, validate=is_date)


def test_env_iterate():
    env = Env(TEST=0)
    env.register(re.compile("re"))
    for key in env:
        assert isinstance(key, str)


def test_env_iterate_rawkeys():
    env = Env(TEST=0)
    r = re.compile("re")
    env.register(r)
    saw_regex = False
    for key in env.rawkeys():
        if isinstance(key, str):
            continue
        elif isinstance(key, type(r)) and key.pattern == "re":
            saw_regex = True
    assert saw_regex


def test_env_get_defaults():
    """Verify the rather complex rules for env.get("<envvar>",default) value when envvar is not defined."""

    env = Env(TEST1=0)
    env.register("TEST_REG", default="abc")
    env.register("TEST_REG_DNG", default=DefaultNotGiven)

    # var is defined, registered is don't-care => value is defined value
    assert env.get("TEST1", 22) == 0
    # var not defined, not registered => value is immediate default
    assert env.get("TEST2", 22) == 22
    assert "TEST2" not in env
    # var not defined, is registered, reg default is not sentinel => value is *registered* default
    assert env.get("TEST_REG", 22) == "abc"
    assert "TEST_REG" in env
    # var not defined, is registered, reg default is sentinel => value is *immediate* default
    assert env.get("TEST_REG_DNG", 22) == 22
    assert "TEST_REG_DNG" not in env


@pytest.mark.parametrize(
    "val,validator",
    [
        ("string", "is_string"),
        (1, "is_int"),
        (0.5, "is_float"),
    ],
)
def test_var_with_default_initer(val, validator):
    var = Var.with_default(val)
    assert var.validate.__name__ == validator
