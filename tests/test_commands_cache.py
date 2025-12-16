import os
import pickle
import stat
import time
from tempfile import TemporaryDirectory

import pytest

from xonsh.commands_cache import (
    SHELL_PREDICTOR_PARSER,
    CaseInsensitiveDict,
    CommandsCache,
    _Commands,
    executables_in,
    predict_false,
    predict_shell,
    predict_true,
)
from xonsh.platform import ON_WINDOWS
from xonsh.pytest.tools import skip_if_on_windows

PATHEXT_ENV = {"PATHEXT": [".COM", ".EXE", ".BAT"]}


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

    paths = [subdir2, subdir1]
    cache = CommandsCache({"PATH": paths})
    cached = cache.update_cache()

    # Check there are no changes after update cache.
    c1 = cache._update_and_check_changes(paths)
    c2 = cache._update_and_check_changes(paths)
    c3 = cache._update_and_check_changes(paths)
    assert [c1, c2, c3] == [True, False, False]

    assert file1.samefile(cached[basename][0])

    # give the os enough time to update the mtime field of the parent directory
    # (represented in seconds on Linux and Windows systems)
    time.sleep(2)
    file2.touch()
    file2.chmod(0o755)

    cached = cache.update_cache()

    assert file2.samefile(cached[basename][0])


@pytest.fixture
def faux_binary(tmp_path):
    """
    A fake binary in the temp path.

    Uses mixed case so tests may make assertions about it.
    """
    binary = tmp_path / "RunMe.exe"
    binary.touch()
    binary.chmod(0o755)
    return binary


def test_find_binary_retains_case(faux_binary):
    cache = CommandsCache({"PATH": []})
    loc = cache.locate_binary(str(faux_binary))
    assert faux_binary.name in loc


def test_exes_in_cwd_are_not_matched(faux_binary, monkeypatch):
    monkeypatch.chdir(faux_binary.parent)
    cache = CommandsCache({"PATH": []})
    assert cache.locate_binary(faux_binary.name) is None


def test_nixos_coreutils(tmp_path):
    """On NixOS the core tools are the symlinks to one universal ``coreutils`` binary file."""
    path = tmp_path / "core"
    coreutils = path / "coreutils"
    echo = path / "echo"
    echo2 = path / "echo2"
    echo3 = path / "echo3"
    cat = path / "cat"

    path.mkdir()
    coreutils.write_bytes(b"Binary with isatty, tcgetattr, tcsetattr.")
    echo.symlink_to(echo2)
    echo2.symlink_to(echo3)
    echo3.symlink_to(coreutils)
    cat.symlink_to(coreutils)

    for toolpath in [coreutils, echo, echo2, echo3, cat]:
        # chmod a+x toolpath
        current_permissions = toolpath.stat().st_mode
        toolpath.chmod(current_permissions | 0o111)

    cache = CommandsCache({"PATH": [path]})

    assert cache.predict_threadable(["echo", "1"]) is True
    assert cache.predict_threadable(["cat", "file"]) is False


def test_executables_in(xession):
    expected = set()
    types = ("file", "directory", "brokensymlink")
    if ON_WINDOWS:
        # Don't test symlinks on windows since it requires admin
        types = ("file", "directory")
    executables = (True, False)
    with TemporaryDirectory() as test_path:
        for _type in types:
            for executable in executables:
                fname = f"{_type}_{executable}"
                if _type == "none":
                    continue
                if _type == "file" and executable:
                    ext = ".exe" if ON_WINDOWS else ""
                    expected.add(fname + ext)
                else:
                    ext = ""
                path = os.path.join(test_path, fname + ext)
                if _type == "file":
                    with open(path, "w") as f:
                        f.write(fname)
                elif _type == "directory":
                    os.mkdir(path)
                elif _type == "brokensymlink":
                    tmp_path = os.path.join(test_path, "i_wont_exist")
                    with open(tmp_path, "w") as f:
                        f.write("deleteme")
                        os.symlink(tmp_path, path)
                    os.remove(tmp_path)
                if executable and not _type == "brokensymlink":
                    os.chmod(path, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
            if ON_WINDOWS:
                xession.env = PATHEXT_ENV
                result = set(executables_in(test_path))
            else:
                result = set(executables_in(test_path))
    assert expected == result


def test_caseinsdict_constructor():
    actual = CaseInsensitiveDict({"key1": "val1", "Key2": "Val2"})
    assert isinstance(actual, CaseInsensitiveDict)
    assert actual["key1"] == "val1"
    assert actual["Key2"] == "Val2"


def test_caseinsdict_getitem():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert actual["Key1"] == "Val1"
    assert actual["key1"] == "Val1"


def test_caseinsdict_setitem():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    actual["Key1"] = "Val2"
    assert actual["Key1"] == "Val2"
    assert actual["key1"] == "Val2"
    actual["key1"] = "Val3"
    assert actual["Key1"] == "Val3"
    assert actual["key1"] == "Val3"


def test_caseinsdict_delitem():
    actual = CaseInsensitiveDict({"Key1": "Val1", "Key2": "Val2"})
    del actual["Key1"]
    assert actual == CaseInsensitiveDict({"Key2": "Val2"})
    del actual["key2"]
    assert actual == CaseInsensitiveDict({})


def test_caseinsdict_contains():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert actual.__contains__("Key1")
    assert actual.__contains__("key1")
    assert not actual.__contains__("key2")


def test_caseinsdict_get():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert actual.get("Key1") == "Val1"
    assert actual.get("key1") == "Val1"
    assert actual.get("key2", "no val") == "no val"
    assert actual.get("key1", "no val") == "Val1"


def test_caseinsdict_update():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    actual.update({"Key2": "Val2"})
    assert actual["key2"] == "Val2"


def test_caseinsdict_keys():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert next(actual.keys()) == "Key1"


def test_caseinsdict_items():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert next(actual.items()) == ("Key1", "Val1")


def test_caseinsdict_repr():
    actual = CaseInsensitiveDict({"Key1": "Val1"})
    assert actual.__repr__() == "CaseInsensitiveDict({'Key1': 'Val1'})"


def test_caseinsdict_copy():
    initial = CaseInsensitiveDict({"Key1": "Val1"})
    actual = initial.copy()
    assert actual == initial
    assert id(actual) != id(initial)
