# -*- coding: utf-8 -*-
"""Testing built_ins.Aliases"""
from __future__ import unicode_literals, print_function

import os

import pytest

import xonsh.built_ins as built_ins
from xonsh.aliases import Aliases
from xonsh.environ import Env

from tools import skip_if_on_windows


def cd(args, stdin=None):
    return args


ALIASES = Aliases(
    {"o": ["omg", "lala"]},
    color_ls=["ls", "--color=true"],
    ls="ls '-  -'",
    cd=cd,
    indirect_cd="cd ..",
)
RAW = ALIASES._raw


def test_imports():
    expected = {
        "o": ["omg", "lala"],
        "ls": ["ls", "-  -"],
        "color_ls": ["ls", "--color=true"],
        "cd": cd,
        "indirect_cd": ["cd", ".."],
    }
    assert RAW == expected


def test_eval_normal(xonsh_builtins):
    assert ALIASES.get("o") == ["omg", "lala"]


def test_eval_self_reference(xonsh_builtins):
    assert ALIASES.get("ls") == ["ls", "-  -"]


def test_eval_recursive(xonsh_builtins):
    assert ALIASES.get("color_ls") == ["ls", "-  -", "--color=true"]


@skip_if_on_windows
def test_eval_recursive_callable_partial(xonsh_builtins):
    xonsh_builtins.__xonsh__.env = Env(HOME=os.path.expanduser("~"))
    assert ALIASES.get("indirect_cd")(["arg2", "arg3"]) == ["..", "arg2", "arg3"]
