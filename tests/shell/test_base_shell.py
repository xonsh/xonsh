"""(A down payment on) Testing for ``xonsh.shells.base_shell.BaseShell`` and associated classes"""

import io
import os

import pytest

from xonsh.shell import deindent, transform_command
from xonsh.shells.base_shell import BaseShell, _TeeStdBuf


@pytest.mark.parametrize(
    "src, expected",
    [
        # single-line indented input
        ("  echo 1\n", "echo 1\n"),
        ("\techo 1\n", "echo 1\n"),
        # no leading whitespace - untouched
        ("echo 1\n", "echo 1\n"),
        # multi-line block with common leading indent (Python paste case)
        (
            "    if True:\n        x = 1\n    print(x)\n",
            "if True:\n    x = 1\nprint(x)\n",
        ),
        # multi-line subproc with common leading indent
        ("  echo 1\n  echo 2\n", "echo 1\necho 2\n"),
        # first line deeper than continuation -- line-continuation subproc
        # paste: dedent alone leaves line 1 indented, so lstrip kicks in
        ("        echo 1 \\\n    2\n", "echo 1 \\\n2\n"),
        # first line deeper but no continuation -- lstrip does NOT fire,
        # so the (already-broken) indent structure is preserved as-is
        ("        echo 1\n    echo 2\n", "    echo 1\necho 2\n"),
        # empty string
        ("", ""),
    ],
)
def test_deindent(src, expected):
    assert deindent(src) == expected


def test_pwd_tracks_cwd(xession, xonsh_execer, tmpdir_factory, monkeypatch):
    asubdir = str(tmpdir_factory.mktemp("asubdir"))
    cur_wd = os.getcwd()
    xession.env.update(
        dict(PWD=cur_wd, XONSH_CACHE_SCRIPTS=False, XONSH_CACHE_EVERYTHING=False)
    )

    monkeypatch.setattr(xonsh_execer, "cacheall", False, raising=False)
    bc = BaseShell(xonsh_execer, None)

    assert os.getcwd() == cur_wd

    bc.default('os.chdir(r"' + asubdir + '")')

    assert os.path.abspath(os.getcwd()) == os.path.abspath(asubdir)
    assert os.path.abspath(os.getcwd()) == os.path.abspath(xession.env["PWD"])
    assert "OLDPWD" in xession.env
    assert os.path.abspath(cur_wd) == os.path.abspath(xession.env["OLDPWD"])


def test_transform(xession):
    @xession.builtins.events.on_transform_command
    def spam2egg(cmd, **_):
        if cmd == "spam":
            return "egg"
        else:
            return cmd

    assert transform_command("spam") == "egg"
    assert transform_command("egg") == "egg"
    assert transform_command("foo") == "foo"


def test_transform_returns_none_is_noop(xession):
    @xession.builtins.events.on_transform_command
    def forget_return(cmd, **_):
        if cmd.strip() == "ls":
            return "echo ls"

    assert transform_command("ls") == "echo ls"
    assert transform_command("echo 1") == "echo 1"


def test_transform_infinite_loop_breaks(xession, monkeypatch):
    """transform_command should stop after recursion limit, not loop forever."""
    monkeypatch.setattr("sys.getrecursionlimit", lambda: 5)
    counter = {"n": 0}

    @xession.builtins.events.on_transform_command
    def flip(cmd, **_):
        counter["n"] += 1
        return "b" if cmd == "a" else "a"

    # print_exception may fail outside except block; we only care the loop stops
    try:
        transform_command("a", show_diff=False)
    except TypeError:
        pass
    assert counter["n"] == 5


@pytest.mark.parametrize(
    "cmd,exp_append_history",
    [
        ("", False),
        ("# a comment", False),
        ("print('yes')", True),
    ],
)
def test_default_append_history(cmd, exp_append_history, xonsh_session, monkeypatch):
    """Test that running an empty line or a comment does not append to history"""
    append_history_calls = []

    monkeypatch.setattr(xonsh_session.history, "append", append_history_calls.append)
    xonsh_session.shell.default(cmd)
    if exp_append_history:
        assert len(append_history_calls) == 1
    else:
        assert len(append_history_calls) == 0


def test_prompt_subproc_does_not_leak_rtn(xonsh_session):
    """A subprocess run during prompt rendering must not pollute
    hist.last_cmd_rtn for the next pure-Python command.

    Regression test for #4912.
    """
    hist = xonsh_session.history

    # Simulate a prompt field that ran a failing subprocess:
    # CommandPipeline._apply_to_history() would have done this.
    hist.last_cmd_rtn = 222

    # Now the user executes a pure-Python expression.
    xonsh_session.shell.default("2+2")

    # The env var must reflect success, not the prompt field's code.
    assert xonsh_session.env["LAST_RETURN_CODE"] == 0


def test_precmd_does_not_strip(xession, xonsh_execer):
    """precmd() must preserve leading whitespace."""
    shell = BaseShell(xonsh_execer, None)
    assert shell.precmd("  echo test") == "  echo test"
    assert shell.precmd("\techo test") == "\techo test"
    assert shell.precmd("echo test") == "echo test"


@pytest.mark.parametrize(
    "prefix",
    ["", "  ", "\t", " \t "],
)
def test_on_precommand_preserves_leading_whitespace(prefix, xonsh_session):
    """on_precommand must receive the command with original leading whitespace."""
    fired = []

    @xonsh_session.builtins.events.on_precommand
    def capture(cmd, **_):
        fired.append(cmd)

    xonsh_session.shell.default(prefix + "print('test')")
    assert len(fired) == 1
    assert fired[0].startswith(prefix + "print")


def test_on_postcommand_preserves_leading_whitespace(xonsh_session):
    """on_postcommand must also receive the command with original whitespace."""
    fired = []

    @xonsh_session.builtins.events.on_postcommand
    def capture(cmd, **_):
        fired.append(cmd)

    xonsh_session.shell.default("  print('test')")
    assert len(fired) == 1
    assert fired[0].startswith("  print")


def test_on_transform_command_receives_leading_whitespace(xonsh_session):
    """on_transform_command must receive the original command with whitespace."""
    received = []

    @xonsh_session.builtins.events.on_transform_command
    def capture(cmd, **_):
        received.append(cmd)
        return cmd

    xonsh_session.shell.default("  print('test')")
    assert len(received) >= 1
    assert received[0].startswith("  print")


def test_src_starts_with_space_without_raw_line(xonsh_session):
    """src_starts_with_space must detect leading whitespace (readline path)."""
    xonsh_session.shell.default("  print('test')")
    assert xonsh_session.shell.src_starts_with_space is True


def test_src_starts_with_space_no_prefix(xonsh_session):
    """src_starts_with_space must be False when there is no leading whitespace."""
    xonsh_session.shell.default("print('test')")
    assert xonsh_session.shell.src_starts_with_space is False


class TestTeeStdBuf:
    def test_readinto_binary_preserves_stdbuf_data(self, xession):
        """readinto() must fill the buffer from stdbuf (the real stdout)
        and mirror the bytes into membuf, not the other way around."""
        stdbuf = io.BytesIO(b"real stdout data")
        membuf = io.BytesIO()
        tee = _TeeStdBuf(stdbuf, membuf)

        dest = bytearray(16)
        n = tee.readinto(dest)
        assert n == 16
        assert bytes(dest[:n]) == b"real stdout data"
        # membuf should have received the same bytes
        assert membuf.getvalue() == b"real stdout data"

    def test_readinto_binary_partial_read(self, xession):
        """readinto() with a buffer larger than available data."""
        stdbuf = io.BytesIO(b"short")
        membuf = io.BytesIO()
        tee = _TeeStdBuf(stdbuf, membuf)

        dest = bytearray(100)
        n = tee.readinto(dest)
        assert n == 5
        assert bytes(dest[:n]) == b"short"
        assert membuf.getvalue() == b"short"
