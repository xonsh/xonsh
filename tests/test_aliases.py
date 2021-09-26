# -*- coding: utf-8 -*-
"""Testing built_ins.Aliases"""
from __future__ import unicode_literals, print_function

import os

import pytest
import inspect

from xonsh.aliases import Aliases, ExecAlias
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


def test_imports(xonsh_builtins):
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


def test_eval_normal(xonsh_builtins):
    ales = make_aliases()
    assert ales.get("o") == ["omg", "lala"]


def test_eval_self_reference(xonsh_builtins):
    ales = make_aliases()
    assert ales.get("ls") == ["ls", "-  -"]


def test_eval_recursive(xonsh_builtins):
    ales = make_aliases()
    assert ales.get("color_ls") == ["ls", "-  -", "--color=true"]


@skip_if_on_windows
def test_eval_recursive_callable_partial(xonsh_execer, xession):
    ales = make_aliases()
    xession.env = Env(HOME=os.path.expanduser("~"))
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


def test_recursive_callable_partial_all(xonsh_builtins):
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


def test_recursive_callable_partial_handles(xonsh_builtins):
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


def test_recursive_callable_partial_none(xonsh_builtins):
    ales = Aliases({"rtn": _return_to_sender_none, "rtn-recurse": ["rtn"]})
    alias = ales.get("rtn-recurse")
    assert callable(alias)
    args, obs = alias()
    assert args == "wakka"
    assert len(obs) == 0


@pytest.mark.parametrize(
    "alias",
    [
        "echo 'hi' and echo 'there'",
        "echo 'hi' or echo 'there'",
        "echo 'hi' && echo 'there'",
        "echo 'hi' || echo 'there'",
        "echo 'hi';  echo 'there'",
    ],
)
def test_subprocess_logical_operators(xonsh_builtins, alias):
    ales = make_aliases()
    ales["echocat"] = alias
    assert isinstance(ales["echocat"], ExecAlias)


@pytest.mark.parametrize(
    "alias",
    [
        "echo 'hi' | grep h",
        "echo 'hi' > file",
        "cat < file",
        "COMMAND1 e>o < input.txt | COMMAND2 > output.txt e>> errors.txt",
        "echo 'h|i' | grep h",
        "echo 'h|i << x > 3' | grep x",
    ],
)
def test_subprocess_io_operators(xonsh_builtins, alias):
    ales = make_aliases()
    ales["echocat"] = alias
    assert isinstance(ales["echocat"], ExecAlias)


@pytest.mark.parametrize(
    "alias",
    [
        {"echocat": "ls"},
    ],
)
def test_dict_merging(xonsh_builtins, alias):
    ales = make_aliases()
    assert (ales | alias)["echocat"] == ["ls"]
    assert (alias | ales)["echocat"] == ["ls"]
    assert "echocat" not in ales


@pytest.mark.parametrize(
    "alias",
    [
        {"echocat": "echo Why do people still use python2.7?"},
        {"echocat": "echo Why?"},
    ],
)
def test_dict_merging_assignment(xonsh_builtins, alias):
    ales = make_aliases()
    ales |= alias

    assert "echocat" in ales
    assert " ".join(ales["echocat"]) == alias["echocat"]

    ales = make_aliases()
    alias |= ales

    assert "o" in alias
    assert alias["o"] == ales["o"]


def test_exec_alias_args(xonsh_builtins):
    stack = inspect.stack()
    try:
        ExecAlias("myargs = $args")(["arg0"], stack=stack)
        ExecAlias("myarg0 = $arg0")(["arg0"], stack=stack)
    except KeyError:
        assert False  # noqa

    assert stack[0][0].f_locals["myargs"] == ["arg0"]
    assert stack[0][0].f_locals["myarg0"] == "arg0"
