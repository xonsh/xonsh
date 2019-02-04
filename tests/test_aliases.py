# -*- coding: utf-8 -*-
"""Testing built_ins.Aliases"""
from __future__ import unicode_literals, print_function

import os

import pytest

import xonsh.built_ins as built_ins
from xonsh.aliases import Aliases
from xonsh.environ import Env

from tools import skip_if_on_windows


def cd(args, stdin=None, **kwargs):
    return args


def make_aliases():
    ales = Aliases(
        {"o": ["omg", "lala"]},
        color_ls=["ls", "--color=true"],
        ls="ls '-  -'",
        cd=cd,
        indirect_cd="cd ..",
    )
    return ales


def test_imports(xonsh_execer, xonsh_builtins):
    ales = make_aliases()
    expected = {
        "o": ["omg", "lala"],
        "ls": ["ls", "-  -"],
        "color_ls": ["ls", "--color=true"],
        "cd": cd,
        "indirect_cd": ["cd", ".."],
    }
    raw = ales._raw
    assert raw == expected


def test_eval_normal(xonsh_execer, xonsh_builtins):
    ales = make_aliases()
    assert ales.get("o") == ["omg", "lala"]


def test_eval_self_reference(xonsh_execer, xonsh_builtins):
    ales = make_aliases()
    assert ales.get("ls") == ["ls", "-  -"]


def test_eval_recursive(xonsh_execer, xonsh_builtins):
    ales = make_aliases()
    assert ales.get("color_ls") == ["ls", "-  -", "--color=true"]


@skip_if_on_windows
def test_eval_recursive_callable_partial(xonsh_execer, xonsh_builtins):
    ales = make_aliases()
    xonsh_builtins.__xonsh__.env = Env(HOME=os.path.expanduser("~"))
    assert ales.get("indirect_cd")(["arg2", "arg3"]) == ["..", "arg2", "arg3"]


def _return_to_sender_all(args, stdin, stdout, stderr, spec, stack):
    return (
        args,
        {
            "stdin": stdin,
            "stdout": stdout,
            "stderr": stderr,
            "spec": spec,
            "stack": stack,
        },
    )


def test_recursive_callable_partial_all(xonsh_execer, xonsh_builtins):
    ales = Aliases({"rtn": _return_to_sender_all, "rtn-recurse": ["rtn", "arg1"]})
    alias = ales.get("rtn-recurse")
    assert callable(alias)
    args, obs = alias(["arg2"], stdin="a", stdout="b", stderr="c", spec="d", stack="e")
    assert args == ["arg1", "arg2"]
    assert len(obs) == 5
    exp = {"stdin": "a", "stdout": "b", "stderr": "c", "spec": "d", "stack": "e"}
    assert obs == exp


def _return_to_sender_handles(args, stdin, stdout, stderr):
    return args, {"stdin": stdin, "stdout": stdout, "stderr": stderr}


def test_recursive_callable_partial_handles(xonsh_execer, xonsh_builtins):
    ales = Aliases({"rtn": _return_to_sender_handles, "rtn-recurse": ["rtn", "arg1"]})
    alias = ales.get("rtn-recurse")
    assert callable(alias)
    args, obs = alias(["arg2"], stdin="a", stdout="b", stderr="c")
    assert args == ["arg1", "arg2"]
    assert len(obs) == 3
    exp = {"stdin": "a", "stdout": "b", "stderr": "c"}
    assert obs == exp


def _return_to_sender_none():
    return "wakka", {}


def test_recursive_callable_partial_none(xonsh_execer, xonsh_builtins):
    ales = Aliases({"rtn": _return_to_sender_none, "rtn-recurse": ["rtn"]})
    alias = ales.get("rtn-recurse")
    assert callable(alias)
    args, obs = alias()
    assert args == "wakka"
    assert len(obs) == 0
