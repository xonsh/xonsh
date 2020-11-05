"""
Tests for command pipelines.
"""

import os
import pytest
import builtins

from xonsh.platform import ON_WINDOWS
from xonsh.procs.pipelines import CommandPipeline
from tests.tools import skip_if_on_windows, skip_if_on_unix


@pytest.fixture(autouse=True)
def patched_events(monkeypatch, xonsh_events, xonsh_execer):
    # needed for ci tests
    monkeypatch.setattr('builtins.events', xonsh_events, raising=False)
    monkeypatch.setitem(builtins.__xonsh__.env, 'RAISE_SUBPROC_ERROR', False)  # for the failing `grep` commands
    if ON_WINDOWS:
        monkeypatch.setattr('builtins.aliases', {
            "echo": "cmd /c echo".split(),
            "grep": "cmd /c findstr".split(),
        }, raising=False)


@pytest.mark.parametrize("cmdline, stdout, stderr", (
        ("!(echo hi)", "hi\n", ""),
        ("!(echo hi o>e)", "", "hi\n"),

        pytest.param("![echo hi]", "hi\n", "", marks=pytest.mark.xfail(
            ON_WINDOWS, reason="ConsoleParallelReader doesn't work without a real console")),
        pytest.param("![echo hi o>e]", "", "hi\n", marks=pytest.mark.xfail(
            ON_WINDOWS, reason="stderr isn't captured in ![] on windows")),

        pytest.param(r"!(echo 'hi\nho')", "hi\nho\n", "", marks=skip_if_on_windows),  # won't work with cmd
        # for some reason cmd's echo adds an extra space:
        pytest.param(r"!(cmd /c 'echo hi && echo ho')", "hi \nho\n", "", marks=skip_if_on_unix),

        ("!(echo hi | grep h)", "hi\n", ""),
        ("!(echo hi | grep x)", "", ""),
))
def test_command_pipeline_capture(cmdline, stdout, stderr, xonsh_execer):
    pipeline: CommandPipeline = xonsh_execer.eval(cmdline)
    assert pipeline.out == stdout
    assert pipeline.err == (stderr or None)
    assert pipeline.raw_out == stdout.replace("\n", os.linesep).encode()
    assert pipeline.raw_err == stderr.replace("\n", os.linesep).encode()


@pytest.mark.parametrize("cmdline, output", (
        ("echo hi", "hi\n"),
        ("echo hi | grep h", "hi\n"),
        ("echo hi | grep x", ""),
        pytest.param("echo -n hi", "hi", marks=skip_if_on_windows),
))
def test_simple_capture(cmdline, output, xonsh_execer):
    assert xonsh_execer.eval(f"$({cmdline})") == output


def test_raw_substitution(xonsh_execer):
    assert xonsh_execer.eval("$(echo @(b'bytes!'))") == "bytes!\n"
