import os
import pickle
import time

import pytest

from xonsh.commands_cache import (
    SHELL_PREDICTOR_PARSER,
    CommandsCache,
    _Commands,
    predict_false,
    predict_shell,
    predict_true,
)
from xonsh.pytest.tools import skip_if_on_windows


def test_commands_cache_lazy(xession):
    cc = xession.commands_cache
    assert not cc.lazyin("xonsh")
    assert 0 == len(list(cc.lazyiter()))
    assert 0 == cc.lazylen()


def test_predict_threadable_unknown_command(xession):
    result = xession.commands_cache.predict_threadable(["command_should_not_found"])
    assert isinstance(result, bool)


class TestCommandsCacheSaveIntermediate:
    """test behavior when $COMMANDS_CACHE_SAVE_INTERMEDIATE=True"""

    @pytest.fixture
    def exin_mock(self, xession, mock_executables_in):
        xession.env["COMMANDS_CACHE_SAVE_INTERMEDIATE"] = True
        return mock_executables_in(["bin1", "bin2"])

    def test_caching_to_file(self, exin_mock, xession, tmp_path):
        assert [b.lower() for b in xession.commands_cache.all_commands.keys()] == [
            "bin1",
            "bin2",
        ]

        files = tmp_path.glob("*.pickle")
        assert len(list(files)) == 1
        exin_mock.assert_called_once()

    def test_loading_cache(self, exin_mock, tmp_path, xession):
        cc = xession.commands_cache
        file = tmp_path / CommandsCache.CACHE_FILE
        file.touch()
        cached = {
            str(tmp_path): _Commands(
                mtime=tmp_path.stat().st_mtime, cmds=("bin1", "bin2")
            )
        }

        file.write_bytes(pickle.dumps(cached))
        assert str(cc.cache_file) == str(file)
        assert [b.lower() for b in cc.all_commands.keys()] == ["bin1", "bin2"]
        exin_mock.assert_not_called()


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
    assert predict_shell(args, None)


FALSE_SHELL_ARGS = [[], ["-c"], ["-i"], ["-i", "-l"]]


@pytest.mark.parametrize("args", FALSE_SHELL_ARGS)
def test_predict_shell_false(args):
    assert not predict_shell(args, None)


PATTERN_BIN_USING_TTY_OR_NOT = [
    (
        False,
        {10: b"isnotatty"},
    ),
    (
        False,
        {12: b"isatty"},
    ),
    (
        False,
        {151: b"gpm"},
    ),
    (
        False,
        {10: b"isatty", 100: b"tcgetattr"},
    ),
    (
        False,
        {10: b"isatty", 100: b"tcsetattr"},
    ),
    (
        True,
        {10: b"isatty", 100: b"tcsetattr", 1000: b"tcgetattr"},
    ),
    (
        True,
        {1000: b"libncurses"},
    ),
    (
        True,
        {4094: b"libgpm"},
    ),
    (
        True,
        {2045: b"tcgetattr", 4095: b"tcgetattr", 6140: b"tcsetattr", 8190: b"isatty"},
    ),
]


@pytest.mark.parametrize("args", PATTERN_BIN_USING_TTY_OR_NOT)
@skip_if_on_windows
def test_commands_cache_predictor_default(args, xession, tmp_path):
    use_tty, patterns = args
    file = tmp_path / "testfile"
    where = list(patterns.keys())
    where.sort()

    with file.open("wb") as f:
        pos = 0
        for w in where:
            f.write(b"\x20" * (w - pos))
            f.write(patterns[w])
            pos = w + len(patterns[w])

        f.write(b"\x20" * (pos // 2))

    result = xession.commands_cache.default_predictor_readbin(
        "", str(file), timeout=1, failure=None
    )
    expected = predict_false if use_tty else predict_true
    assert result == expected


class Test_is_only_functional_alias:
    @skip_if_on_windows
    def test_cd(self, xession):
        xession.aliases["cd"] = lambda args: os.chdir(args[0])
        xession.env["PATH"] = []
        assert xession.commands_cache.is_only_functional_alias("cd")

    def test_non_exist(self, xession):
        assert (
            xession.commands_cache.is_only_functional_alias(
                "<not really a command name>"
            )
            is False
        )

    def test_bash_and_is_alias_is_only_functional_alias(self, xession):
        xession.aliases["git"] = lambda args: os.chdir(args[0])
        assert xession.commands_cache.is_only_functional_alias("git") is False


def test_update_cache(xession, tmp_path):
    xession.env["ENABLE_COMMANDS_CACHE"] = False
    basename = "PITA.EXE"
    subdir1 = tmp_path / "subdir1"
    subdir2 = tmp_path / "subdir2"
    subdir1.mkdir()
    subdir2.mkdir()
    file1 = subdir1 / basename
    file2 = subdir2 / basename
    file1.touch()
    file1.chmod(0o755)

    cache = CommandsCache({"PATH": [subdir2, subdir1]})
    cached = cache.update_cache()

    assert file1.samefile(cached[basename][0])

    # give the os enough time to update the mtime field of the parent directory
    # (represented in seconds on Linux and Windows systems)
    time.sleep(2)
    file2.touch()
    file2.chmod(0o755)

    cached = cache.update_cache()

    assert file2.samefile(cached[basename][0])
