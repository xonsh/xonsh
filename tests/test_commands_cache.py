import os
import pickle
import time
from unittest.mock import MagicMock

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


def test_predict_threadable_unknown_command(xonsh_builtins):
    cc = CommandsCache()
    result = cc.predict_threadable(["command_should_not_found"])
    assert isinstance(result, bool)


@pytest.fixture
def commands_cache_tmp(xession, tmp_path, monkeypatch, patch_commands_cache_bins):
    xession.env["XONSH_DATA_DIR"] = tmp_path
    xession.env["COMMANDS_CACHE_SAVE_INTERMEDIATE"] = True
    return patch_commands_cache_bins(["bin1", "bin2"])


def test_commands_cached_between_runs(commands_cache_tmp, tmp_path):
    # 1. no pickle file
    # 2. return empty result first and create a thread to populate result
    # 3. once the result is available then next call to cc.all_commands returns

    cc = commands_cache_tmp

    # wait for thread to end
    cnt = 0  # timeout waiting for thread
    while True:
        if cc.all_commands or cnt > 10:
            break
        cnt += 1
        time.sleep(0.1)
    assert [b.lower() for b in cc.all_commands.keys()] == ["bin1", "bin2"]

    files = tmp_path.glob("*.pickle")
    assert len(list(files)) == 1

    # cleanup dir
    for file in files:
        os.remove(file)


def test_commands_cache_uses_pickle_file(commands_cache_tmp, tmp_path, monkeypatch):
    cc = commands_cache_tmp
    update_cmds_cache = MagicMock()
    monkeypatch.setattr(cc, "_update_cmds_cache", update_cmds_cache)
    file = tmp_path / CommandsCache.CACHE_FILE
    bins = {
        "bin1": (
            "/some-path/bin1",
            None,
        ),
        "bin2": (
            "/some-path/bin2",
            None,
        ),
    }

    file.write_bytes(pickle.dumps(bins))
    assert cc.all_commands == bins
    assert cc._loaded_pickled


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
def test_commands_cache_predictor_default(args, xonsh_builtins):
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
def test_cd_is_only_functional_alias(xession):
    cc = CommandsCache()
    xession.aliases["cd"] = lambda args: os.chdir(args[0])
    assert cc.is_only_functional_alias("cd")


def test_non_exist_is_only_functional_alias(xonsh_builtins):
    cc = CommandsCache()
    assert not cc.is_only_functional_alias("<not really a command name>")


@skip_if_on_windows
def test_bash_is_only_functional_alias(xession):
    xession.env["PATH"] = os.environ["PATH"].split(os.pathsep)
    cc = CommandsCache()
    assert not cc.is_only_functional_alias("bash")


@skip_if_on_windows
def test_bash_and_is_alias_is_only_functional_alias(xession):
    xession.env["PATH"] = os.environ["PATH"].split(os.pathsep)
    cc = CommandsCache()
    xession.aliases["bash"] = lambda args: os.chdir(args[0])
    assert not cc.is_only_functional_alias("bash")
