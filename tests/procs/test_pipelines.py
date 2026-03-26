"""
Tests for command pipelines.
"""

import os
import signal
import threading

import pytest

from xonsh.platform import ON_WINDOWS
from xonsh.procs.pipelines import CommandPipeline
from xonsh.pytest.tools import (
    VER_MAJOR_MINOR,
    skip_if_on_unix,
    skip_if_on_windows,
)

# TODO: track down which pipeline + spec test is hanging CI
# Skip entire test file for Linux on Python 3.12
pytestmark = pytest.mark.skipif(
    not ON_WINDOWS and VER_MAJOR_MINOR == (3, 12),
    reason="Backgrounded test is hanging on CI on 3.12 only",
    allow_module_level=True,
)


@pytest.fixture(autouse=True)
def patched_events(monkeypatch, xonsh_events, xonsh_session):
    from xonsh.procs.jobs import get_tasks

    get_tasks().clear()
    # needed for ci tests
    monkeypatch.setitem(
        xonsh_session.env, "RAISE_SUBPROC_ERROR", False
    )  # for the failing `grep` commands
    monkeypatch.setitem(
        xonsh_session.env, "XONSH_CAPTURE_ALWAYS", True
    )  # capture output of ![]
    if ON_WINDOWS:
        monkeypatch.setattr(
            xonsh_session.commands_cache,
            "aliases",
            {
                "echo": "cmd /c echo".split(),
                "grep": "cmd /c findstr".split(),
            },
            raising=False,
        )


@pytest.mark.parametrize(
    "cmdline, stdout, stderr, raw_stdout",
    (
        ("!(echo hi)", "hi", "", "hi\n"),
        ("!(echo hi o>e)", "", "hi\n", ""),
        pytest.param(
            "![echo hi]",
            "hi",
            "",
            "hi\n",
            marks=pytest.mark.xfail(
                ON_WINDOWS,
                reason="ConsoleParallelReader doesn't work without a real console",
            ),
        ),
        pytest.param(
            "![echo hi o>e]",
            "",
            "hi\n",
            "",
            marks=pytest.mark.xfail(
                ON_WINDOWS, reason="stderr isn't captured in ![] on windows"
            ),
        ),
        pytest.param(
            r"!(echo 'hi\nho')", "hi\nho\n", "", "hi\nho\n", marks=skip_if_on_windows
        ),  # won't work with cmd
        # for some reason cmd's echo adds an extra space:
        pytest.param(
            r"!(cmd /c 'echo hi && echo ho')",
            "hi \nho\n",
            "",
            "hi \nho\n",
            marks=skip_if_on_unix,
        ),
        ("!(echo hi | grep h)", "hi", "", "hi\n"),
        ("!(echo hi | grep x)", "", "", ""),
    ),
)
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_command_pipeline_capture(cmdline, stdout, stderr, raw_stdout, xonsh_execer):
    pipeline: CommandPipeline = xonsh_execer.eval(cmdline)
    assert pipeline.out == stdout
    assert pipeline.err == (stderr or None)
    assert pipeline.raw_out == raw_stdout.replace("\n", os.linesep).encode()
    assert pipeline.raw_err == stderr.replace("\n", os.linesep).encode()


@pytest.mark.parametrize(
    "cmdline, output",
    (
        ("echo hi", "hi"),
        ("echo hi | grep h", "hi"),
        ("echo hi | grep x", ""),
        pytest.param("echo -n hi", "hi", marks=skip_if_on_windows),
    ),
)
def test_simple_capture(cmdline, output, xonsh_execer):
    assert xonsh_execer.eval(f"$({cmdline})") == output


def test_raw_substitution(xonsh_execer):
    assert xonsh_execer.eval("$(echo @(b'bytes!'))") == "bytes!"


@pytest.mark.parametrize(
    "cmdline, result",
    (
        ("bool(!(echo 1))", True),
        ("bool(!(nocommand))", False),
        ("int(!(echo 1))", 0),
        ("int(!(nocommand))", 1),
        ("hash(!(echo 1))", 0),
        ("hash(!(nocommand))", 1),
        ("str(!(echo 1))", "1"),
        ("str(!(nocommand))", ""),
        ("!(echo 1) == 0", True),
        ("!(nocommand) == 1", True),
        pytest.param("!(echo -n str) == 'str'", True, marks=skip_if_on_windows),
        ("!(nocommand) == ''", True),
    ),
)
def test_casting(cmdline, result, xonsh_execer):
    assert xonsh_execer.eval(f"{cmdline}") == result


@skip_if_on_windows
@skip_if_on_unix
def test_background_pgid(xonsh_session, monkeypatch):
    monkeypatch.setitem(xonsh_session.env, "XONSH_INTERACTIVE", True)
    pipeline = xonsh_session.execer.eval("![echo hi &]")
    assert pipeline.term_pgid is not None


# Windows: The test is skipped on Windows because cmd /c echo can't output arbitrary unicode escape sequences (\u009b, \u019b) — it replaces them with ?. This is a cmd.exe encoding limitation.
@skip_if_on_windows
@pytest.mark.parametrize(
    "cmdline, stdout, stderr, raw_stdout",
    (
        (r'!(echo "\001hidden\002abc")', "abc", "", "\001hidden\002abc\n"),
        (r'!(echo "\u009b36mabc")', "abc", "", "\u009b36mabc\n"),
        (r'!(echo "\u019b36mabc")', "\u019b36mabc", "", "\u019b36mabc\n"),
    ),
)
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_remove_hide_escape(cmdline, stdout, stderr, raw_stdout, xonsh_execer):
    pipeline = xonsh_execer.eval(cmdline)
    pipeline.end()
    assert pipeline.out == stdout
    assert pipeline.err == (stderr or None)
    assert pipeline.raw_out == raw_stdout.replace("\n", os.linesep).encode()
    assert pipeline.raw_err == stderr.replace("\n", os.linesep).encode()


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_sigint_no_recursion(xonsh_session):
    """Ctrl+C during captured subprocess should not cause RecursionError.

    Regression test: PopenThread._signal_int called pthread_kill(SIGINT) on
    itself without a re-entrancy guard, causing infinite recursion when the
    child process was still alive.
    """
    xonsh_session.env["RAISE_SUBPROC_ERROR"] = False

    # Use a delayed self-signal instead of real Ctrl+C
    def _interrupt():
        import time

        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    t = threading.Thread(target=_interrupt, daemon=True)
    t.start()

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(sleep 10)")
    # If we get here without RecursionError, the fix works.
    # The pipeline should end with KeyboardInterrupt caught internally.
    t.join(timeout=5)


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callable_alias_redirect_e2o(xonsh_session):
    """Callable alias with e>o should merge stderr into stdout.

    Regression test: previously captured_stderr was set to the same pipe reader
    as captured_stdout, causing two NonBlockingFDReaders to race on one fd.
    """

    def _alias():
        print("OUT")
        print("ERR", file=__import__("sys").stderr)

    xonsh_session.aliases["tste2o"] = _alias

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(tste2o e>o)")
    assert "ERR" in pipeline.out
    assert "OUT" in pipeline.out
    assert pipeline.err is None


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callable_alias_redirect_o2e(xonsh_session):
    """Callable alias with o>e should merge stdout into stderr."""

    def _alias():
        print("OUT")
        print("ERR", file=__import__("sys").stderr)

    xonsh_session.aliases["tsto2e"] = _alias

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(tsto2e o>e)")
    assert pipeline.out == ""
    assert "OUT" in pipeline.err
    assert "ERR" in pipeline.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callable_alias_subcmd_redirect_e2o(xonsh_session):
    """Callable alias with e>o: writing to both stdout and stderr params.

    All output should end up in stdout when e>o is used.
    """

    def _alias(args, stdin, stdout, stderr):
        print("O", end="", file=stdout)
        print("E", end="", file=stderr)

    xonsh_session.aliases["tstsube2o"] = _alias

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(tstsube2o e>o)")
    out = pipeline.out
    assert "O" in out
    assert "E" in out
    assert pipeline.err is None
