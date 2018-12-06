# -*- coding: utf-8 -*-
"""Test XonshLexer for pygments"""

import os
import builtins

import pytest
from pygments.token import (
    Keyword,
    Name,
    String,
    Error,
    Number,
    Operator,
    Punctuation,
    Text,
)
from tools import skip_if_on_windows

from xonsh.platform import ON_WINDOWS
from xonsh.built_ins import load_builtins, unload_builtins
from xonsh.execer import Execer
from xonsh.pyghooks import XonshLexer


@pytest.fixture(autouse=True)
def load_command_cache(xonsh_builtins):
    load_builtins()
    if ON_WINDOWS:
        for key in ("cd", "bash"):
            builtins.aliases[key] = lambda *args, **kwargs: None
    yield
    unload_builtins()


def check_token(code, tokens):
    """Make sure that all tokens appears in code in order"""
    lx = XonshLexer()
    tks = list(lx.get_tokens(code))

    for tk in tokens:
        while tks:
            if tk == tks[0]:
                break
            tks = tks[1:]
        else:
            msg = "Token {!r} missing: {!r}".format(tk, list(lx.get_tokens(code)))
            pytest.fail(msg)
            break


@skip_if_on_windows
def test_ls():
    check_token("ls -al", [(Name.Builtin, "ls")])


@skip_if_on_windows
def test_bin_ls():
    check_token("/bin/ls -al", [(Name.Builtin, "/bin/ls")])


@skip_if_on_windows
def test_py_print():
    check_token('print("hello")', [(Keyword, "print"), (String.Double, "hello")])


@skip_if_on_windows
def test_invalid_cmd():
    check_token("non-existance-cmd -al", [(Name, "non")])  # parse as python
    check_token(
        "![non-existance-cmd -al]", [(Error, "non-existance-cmd")]
    )  # parse as error
    check_token("for i in range(10):", [(Keyword, "for")])  # as py keyword
    check_token("(1, )", [(Punctuation, "("), (Number.Integer, "1")])


@skip_if_on_windows
def test_multi_cmd():
    check_token(
        "cd && cd", [(Name.Builtin, "cd"), (Operator, "&&"), (Name.Builtin, "cd")]
    )
    check_token(
        "cd || non-existance-cmd",
        [(Name.Builtin, "cd"), (Operator, "||"), (Error, "non-existance-cmd")],
    )


@skip_if_on_windows
def test_nested():
    check_token(
        'echo @("hello")',
        [
            (Name.Builtin, "echo"),
            (Keyword, "@"),
            (Punctuation, "("),
            (String.Double, "hello"),
            (Punctuation, ")"),
        ],
    )
    check_token(
        "print($(cd))",
        [
            (Keyword, "print"),
            (Punctuation, "("),
            (Keyword, "$"),
            (Punctuation, "("),
            (Name.Builtin, "cd"),
            (Punctuation, ")"),
            (Punctuation, ")"),
        ],
    )
    check_token(
        r'print(![echo "])\""])',
        [
            (Keyword, "print"),
            (Keyword, "!"),
            (Punctuation, "["),
            (Name.Builtin, "echo"),
            (String.Double, r'"])\""'),
            (Punctuation, "]"),
        ],
    )


@skip_if_on_windows
def test_path(tmpdir):
    test_dir = str(tmpdir.mkdir("xonsh-test-highlight-path"))
    check_token(
        "cd {}".format(test_dir), [(Name.Builtin, "cd"), (Name.Constant, test_dir)]
    )
    check_token(
        "cd {}-xxx".format(test_dir),
        [(Name.Builtin, "cd"), (Text, "{}-xxx".format(test_dir))],
    )
    check_token("cd X={}".format(test_dir), [(Name.Constant, test_dir)])

    with builtins.__xonsh__.env.swap(AUTO_CD=True):
        check_token(test_dir, [(Name.Constant, test_dir)])


@skip_if_on_windows
def test_subproc_args():
    check_token("cd 192.168.0.1", [(Text, "192.168.0.1")])


@skip_if_on_windows
def test_backtick():
    check_token(
        r"echo g`.*\w+`",
        [
            (String.Affix, "g"),
            (String.Backtick, "`"),
            (String.Regex, "."),
            (String.Regex, "*"),
            (String.Escape, r"\w"),
        ],
    )


@skip_if_on_windows
def test_macro():
    check_token(
        r"g!(42, *, 65)",
        [(Name, "g"), (Keyword, "!"), (Punctuation, "("), (Number.Integer, "42")],
    )
    check_token(
        r"echo! hello world",
        [(Name.Builtin, "echo"), (Keyword, "!"), (String, "hello world")],
    )
    check_token(
        r"bash -c ! export var=42; echo $var",
        [
            (Name.Builtin, "bash"),
            (Text, "-c"),
            (Keyword, "!"),
            (String, "export var=42; echo $var"),
        ],
    )
