import os
import builtins

import pytest

from xonsh.commands_cache import (
    CommandsCache,
    predict_shell,
    SHELL_PREDICTOR_PARSER,
    predict_true,
    predict_false,
)
from tools import skip_if_on_windows


def test_commands_cache_lazy(xonsh_builtins):
    cc = CommandsCache()
    assert not cc.lazyin("xonsh")
    assert 0 == len(list(cc.lazyiter()))
    assert 0 == cc.lazylen()


TRUE_SHELL_ARGS = [
    ["-c", "yo"],
    ["-c=yo"],
    ["file"],
    ["-i", "-l", "file"],
    ["-i", "-c", "yo"],
    ["-i", "file"],
    ["-i", "-c", "yo", "file"],
]


@pytest.mark.parametrize("args", TRUE_SHELL_ARGS)
def test_predict_shell_parser(args):
    ns, unknown = SHELL_PREDICTOR_PARSER.parse_known_args(args)
    if ns.filename is not None:
        assert not ns.filename.startswith("-")


@pytest.mark.parametrize("args", TRUE_SHELL_ARGS)
def test_predict_shell_true(args):
    assert predict_shell(args)


FALSE_SHELL_ARGS = [[], ["-c"], ["-i"], ["-i", "-l"]]


@pytest.mark.parametrize("args", FALSE_SHELL_ARGS)
def test_predict_shell_false(args):
    assert not predict_shell(args)


PATTERN_BIN_USING_TTY_OR_NOT = [
    (False, {10: b"isnotatty"}),
    (False, {12: b"isatty"}),
    (False, {151: b"gpm"}),
    (False, {10: b"isatty", 100: b"tcgetattr"}),
    (False, {10: b"isatty", 100: b"tcsetattr"}),
    (True, {10: b"isatty", 100: b"tcsetattr", 1000: b"tcgetattr"}),
    (True, {1000: b"libncurses"}),
    (True, {4094: b"libgpm"}),
    (
        True,
        {2045: b"tcgetattr", 4095: b"tcgetattr", 6140: b"tcsetattr", 8190: b"isatty"},
    ),
]


@pytest.mark.parametrize("args", PATTERN_BIN_USING_TTY_OR_NOT)
@skip_if_on_windows
def test_commands_cache_predictor_default(args):
    cc = CommandsCache()
    use_tty, patterns = args
    f = open("testfile", "wb")
    where = list(patterns.keys())
    where.sort()

    pos = 0
    for w in where:
        f.write(b"\x20" * (w - pos))
        f.write(patterns[w])
        pos = w + len(patterns[w])

    f.write(b"\x20" * (pos // 2))
    f.close()

    result = cc.default_predictor_readbin(
        "", os.getcwd() + os.sep + "testfile", timeout=1, failure=None
    )
    expected = predict_false if use_tty else predict_true
    assert result == expected


@skip_if_on_windows
def test_cd_is_only_functional_alias(xonsh_builtins):
    cc = CommandsCache()
    builtins.aliases["cd"] = lambda args: os.chdir(args[0])
    assert cc.is_only_functional_alias("cd")


def test_non_exist_is_only_functional_alias(xonsh_builtins):
    cc = CommandsCache()
    assert not cc.is_only_functional_alias("<not really a command name>")


@skip_if_on_windows
def test_bash_is_only_functional_alias(xonsh_builtins):
    builtins.__xonsh__.env["PATH"] = os.environ["PATH"].split(os.pathsep)
    cc = CommandsCache()
    assert not cc.is_only_functional_alias("bash")


@skip_if_on_windows
def test_bash_and_is_alias_is_only_functional_alias(xonsh_builtins):
    builtins.__xonsh__.env["PATH"] = os.environ["PATH"].split(os.pathsep)
    cc = CommandsCache()
    builtins.aliases["bash"] = lambda args: os.chdir(args[0])
    assert not cc.is_only_functional_alias("bash")
