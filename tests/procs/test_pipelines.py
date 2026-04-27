"""
Tests for command pipelines.
"""

import os

import pytest

from xonsh.aliases import Aliases
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
        xonsh_session.env, "XONSH_SUBPROC_CMD_RAISE_ERROR", False
    )  # for the failing `grep` commands
    monkeypatch.setitem(
        xonsh_session.env, "XONSH_CAPTURE_ALWAYS", True
    )  # capture output of ![]
    if ON_WINDOWS:
        monkeypatch.setattr(
            xonsh_session.commands_cache,
            "aliases",
            Aliases(
                {
                    "echo": "cmd /c echo".split(),
                    "grep": "cmd /c findstr".split(),
                }
            ),
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
def test_simple_capture(cmdline, output, xonsh_execer, xonsh_session, monkeypatch):
    # ``echo hi | grep x`` returns empty stdout with rc=1; the new
    # XONSH_SUBPROC_RAISE_ERROR semantics would raise on it, but this
    # test specifically checks that $() captures the empty string.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_RAISE_ERROR", False)
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
@pytest.mark.timeout(30)
def test_callable_alias_redirect_o2e(xonsh_session):
    """Callable alias with o>e should merge stdout into stderr.

    Hard timeout: this test has been observed to hang indefinitely in
    FreeBSD-CURRENT poudriere build jails (issue #6374). Without
    ``--timeout``, a hang in CI consumes the whole job before pytest
    notices; the explicit mark turns the hang into a quick failure
    with a stacktrace pointing at the deadlock so it can be diagnosed.
    """

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


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callable_alias_o2e_uncaptured(xonsh_session):
    """$[alias o>e] should not crash on int stdout fd.

    Regression test: o>e sets spec.stdout to the int flag 2. For uncaptured
    commands _make_last_spec_captured is never called, so the raw int
    reached iterraw() which called .readable() / .fileno() on it.
    """

    def _alias(args, stdin, stdout, stderr):
        print("O", end="", file=stdout)
        print("E", end="", file=stderr)

    xonsh_session.aliases["tsto2euncap"] = _alias
    # Should not raise AttributeError
    xonsh_session.execer.eval("$[tsto2euncap o>e]")


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_stderr_prefix_postfix(xonsh_session):
    """XONSH_STDERR_PREFIX/POSTFIX should wrap captured stderr output."""
    xonsh_session.env["XONSH_STDERR_PREFIX"] = "PRE"
    xonsh_session.env["XONSH_STDERR_POSTFIX"] = "POST"

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(echo error o>e)")
    assert pipeline.raw_err.startswith(b"PRE")
    assert pipeline.raw_err.endswith(b"POST")
    assert b"error" in pipeline.raw_err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_object_capture_without_threading(capfd, xonsh_session):
    """!() must capture output even when THREAD_SUBPROCS is disabled.

    Regression test: during rc-file loading THREAD_SUBPROCS is set to None,
    which made threadable=False. The old code disabled capture for both
    "object" and "hiddenobject" when not threadable, so !() leaked output
    to the terminal instead of capturing it.
    """
    xonsh_session.env["THREAD_SUBPROCS"] = None

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(echo captured)")
    assert pipeline.out == "captured"
    assert "captured" not in capfd.readouterr().out


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipeline_early_exit_no_hang(xonsh_session):
    """Pipeline where downstream exits before upstream must not deadlock.

    Regression test: when the last process (head) exited, the read end of
    the inter-process pipe was kept open in the parent. Upstream (seq)
    blocked on write() with a full buffer, and iterraw() waited for it
    via _any_proc_running() — deadlock.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    # $() — captured stdout
    out = xonsh_session.execer.eval("$(seq 1000000 | head -n 3)")
    assert out.strip() == "1\n2\n3"

    # !() — captured object
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(seq 1000000 | head -n 3)")
    assert pipeline.out.strip() == "1\n2\n3"


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipeline_early_exit_callable_alias(xonsh_session):
    """Same early-exit scenario but with callable aliases in the pipeline."""
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _many_lines(args, stdin, stdout, stderr):
        for i in range(1, 1000001):
            print(i, file=stdout)

    def _take3(args, stdin, stdout, stderr):
        for i, line in enumerate(stdin):
            stdout.write(line)
            if i >= 2:
                break

    xonsh_session.aliases["manylines"] = _many_lines
    xonsh_session.aliases["take3"] = _take3

    # callable upstream | external downstream
    out = xonsh_session.execer.eval("$(manylines | head -n 3)")
    assert out.strip() == "1\n2\n3"

    # external upstream | callable downstream
    out = xonsh_session.execer.eval("$(seq 1000000 | take3)")
    assert out.strip() == "1\n2\n3"

    # both callable
    out = xonsh_session.execer.eval("$(manylines | take3)")
    assert out.strip() == "1\n2\n3"


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipe_into_callable_alias_no_bad_fd(xonsh_session, capsys):
    """Piping into a callable alias that iterates over stdin must not raise
    'Bad file descriptor'.

    Regression test: when an upstream subprocess (e.g. ``echo``) finished
    quickly, ``CommandPipeline._prev_procs_done`` called ``ch.close()`` on
    the connecting pipe — which closed BOTH ends.  The downstream callable
    alias was still actively iterating over its stdin TextIOWrapper around
    the read end, so the very next ``read()`` failed with
    ``OSError: [Errno 9] Bad file descriptor``.  The proxy thread caught
    the exception, printed it via ``print_exception`` (to xonsh's main
    stderr, not the captured pipeline stderr) and returned exit code 1.

    The fix only closes the *write* end of the connecting pipe in
    ``_prev_procs_done``; the read end is closed later in
    ``_close_prev_procs`` once the downstream proc has actually finished.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _add(args, stdin, stdout, stderr):
        name = args[0] if args else ""
        for line in stdin or []:
            stdout.write(line.upper() + name)

    xonsh_session.aliases["add"] = _add

    # The original failing case from the bug report.
    pipeline: CommandPipeline = xonsh_session.execer.eval(
        "!(echo -n 'hello ' | add snail)"
    )
    pipeline.end()
    captured = capsys.readouterr()
    assert pipeline.out == "HELLO snail"
    assert pipeline.returncode == 0, (
        f"alias proxy returned {pipeline.returncode!r}; "
        f"captured stderr: {captured.err!r}"
    )
    assert "Bad file descriptor" not in captured.err
    assert "Exception in thread" not in captured.err

    # Multiple input lines should also work.
    pipeline = xonsh_session.execer.eval(r"!(printf 'a\nb\nc' | add X)")
    pipeline.end()
    captured = capsys.readouterr()
    assert pipeline.out == "A\nXB\nXCX"
    assert pipeline.returncode == 0
    assert "Bad file descriptor" not in captured.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipe_into_callable_alias_user_exception(xonsh_session, capsys):
    """A user exception inside a callable alias reading stdin must surface
    as the *user's* exception (e.g. ZeroDivisionError), not as the spurious
    "Bad file descriptor" caused by the race in _prev_procs_done.

    Also verifies:
    - output written before the exception is preserved (safe_flush);
    - the pipeline returns non-zero;
    - the user's traceback is what xonsh prints (not an OSError);
    - upstream is properly torn down.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _erradd(args, stdin, stdout, stderr):
        i = 0
        for line in stdin or []:
            if i == 3:
                raise ZeroDivisionError("division by zero")
            stdout.write("GOT:" + line)
            i += 1

    xonsh_session.aliases["erradd"] = _erradd

    pipeline: CommandPipeline = xonsh_session.execer.eval("!(seq 1 100 | erradd)")
    pipeline.end()
    captured = capsys.readouterr()

    # Output produced *before* the user error is preserved.
    assert pipeline.out == "GOT:1\nGOT:2\nGOT:3\n"
    assert pipeline.returncode == 1
    # The user's actual error is reported, not a spurious EBADF.
    assert "ZeroDivisionError" in captured.err
    assert "Bad file descriptor" not in captured.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipe_into_callable_alias_repeated(xonsh_session, capsys):
    """Repeatedly piping a fast-exiting upstream into a callable alias.

    The race condition fixed in ``_prev_procs_done`` is timing-sensitive:
    it triggers when the upstream subprocess finishes between two reads on
    the downstream alias's stdin.  Run the same pipeline many times to make
    a regression unmissable on CI.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _upper(args, stdin, stdout, stderr):
        for line in stdin or []:
            stdout.write(line.upper())

    xonsh_session.aliases["upperalias"] = _upper

    failures = []
    for i in range(20):
        pipeline: CommandPipeline = xonsh_session.execer.eval(
            "!(echo -n 'hello' | upperalias)"
        )
        pipeline.end()
        if pipeline.out != "HELLO" or pipeline.returncode != 0:
            failures.append((i, pipeline.out, pipeline.returncode))
    captured = capsys.readouterr()
    assert not failures, (
        f"{len(failures)}/20 iterations failed: {failures!r}; "
        f"captured stderr: {captured.err!r}"
    )
    assert "Bad file descriptor" not in captured.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipe_into_silent_callable_alias(xonsh_session, capsys):
    """Pipe into a callable alias that reads stdin but writes nothing.

    This is the *widest* race window for the `_prev_procs_done` bug:
    because the alias produces no output, ``iterraw()`` never enters the
    ``if stdout_lines or stderr_lines: check_prev_done = True`` branch and
    keeps falling into ``elif prev_end_time is None: _prev_procs_done()``
    on every loop iteration.  Without the fix, the connecting pipe gets
    closed almost immediately after the upstream subprocess exits, while
    the alias is still draining stdin.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    received: list[str] = []

    def _silent(args, stdin, stdout, stderr):
        for line in stdin or []:
            received.append(line)

    xonsh_session.aliases["silentalias"] = _silent

    failures = []
    for i in range(20):
        received.clear()
        pipeline: CommandPipeline = xonsh_session.execer.eval(
            r"!(printf 'a\nb\nc' | silentalias)"
        )
        pipeline.end()
        if pipeline.returncode != 0 or received != ["a\n", "b\n", "c"]:
            failures.append((i, pipeline.returncode, list(received)))
    captured = capsys.readouterr()
    assert not failures, (
        f"{len(failures)}/20 iterations failed: {failures!r}; "
        f"captured stderr: {captured.err!r}"
    )
    assert "Bad file descriptor" not in captured.err
    assert "Exception in thread" not in captured.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_pipe_into_callable_alias_readline_loop(xonsh_session, capsys):
    """Pipe into a callable alias that uses ``stdin.readline()`` in a loop.

    ``readline()`` follows the same code path as ``for line in stdin``
    (the ``__next__`` of a ``TextIOWrapper`` ultimately calls ``readline``)
    but is a slightly different surface that user code commonly takes.
    Each ``readline()`` is a fresh Python-level call that does its own
    ``os.read``, so the race in ``_prev_procs_done`` can fire between
    successive calls and surface as ``Bad file descriptor``.

    Note: ``stdin.read()`` and ``stdin.readlines()`` are *not* a regression
    surface for this bug — they perform a single Python call that drains
    the pipe internally; the kernel returns EOF (not EBADF) if the fd is
    closed while a blocking ``os.read`` is in progress on macOS/Linux.
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _rl(args, stdin, stdout, stderr):
        n = 0
        while True:
            line = stdin.readline()
            if not line:
                break
            n += 1
            stdout.write(line.upper())
        stdout.write(f"N={n}\n")

    xonsh_session.aliases["rlalias"] = _rl

    failures = []
    for i in range(20):
        pipeline: CommandPipeline = xonsh_session.execer.eval(
            r"!(printf 'a\nb\nc' | rlalias)"
        )
        pipeline.end()
        if pipeline.out != "A\nB\nCN=3\n" or pipeline.returncode != 0:
            failures.append((i, pipeline.out, pipeline.returncode))
    captured = capsys.readouterr()
    assert not failures, (
        f"{len(failures)}/20 iterations failed: {failures!r}; "
        f"captured stderr: {captured.err!r}"
    )
    assert "Bad file descriptor" not in captured.err


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callable_alias_in_middle_of_pipeline(xonsh_session, capsys):
    """A callable alias as the *middle* stage of a 3+ stage pipeline.

    The pipe between the upstream subprocess and the middle alias is owned
    by ``specs[0].pipe_channels`` and goes through the same
    ``_prev_procs_done`` close path.  Without the fix, that pipe gets
    closed mid-iteration and the middle alias hits ``EBADF`` on its next
    ``read``.

    Detection trick: the proxy's ``except OSError`` handler can silently
    swallow the EBADF (r=0) when the downstream side of the alias's
    stdout pipe is also no longer writable, so a simple output assertion
    is not enough.  The middle alias here writes a sentinel ``"DONE\\n"``
    line *after* the ``for line in stdin`` loop — that line is only
    produced when the loop terminates normally via EOF, and is silently
    lost when the loop exits via the EBADF exception.  Asserting on the
    presence of the sentinel reliably distinguishes "buggy completion"
    from "correct completion".
    """
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    def _midupper(args, stdin, stdout, stderr):
        for line in stdin or []:
            stdout.write(line.upper())
        stdout.write("DONE\n")

    xonsh_session.aliases["midupper"] = _midupper

    failures = []
    for i in range(20):
        # subprocess | callable | subprocess
        pipeline: CommandPipeline = xonsh_session.execer.eval(
            "!(echo -n 'hi' | midupper | cat)"
        )
        pipeline.end()
        if pipeline.returncode != 0 or pipeline.out != "HIDONE":
            failures.append(("sub|mid|sub", i, pipeline.out, pipeline.returncode))

        # subprocess | callable | callable
        pipeline = xonsh_session.execer.eval("!(echo -n 'hi' | midupper | midupper)")
        pipeline.end()
        # First midupper writes "HI" + "DONE\n"; second midupper iterates
        # those two lines ("HI", "DONE\n"), uppercases them (still "HI",
        # "DONE\n"), then writes its own sentinel — final output is
        # "HIDONE\nDONE\n".
        if pipeline.returncode != 0 or pipeline.out != "HIDONE\nDONE\n":
            failures.append(("sub|mid|mid", i, pipeline.out, pipeline.returncode))

    captured = capsys.readouterr()
    assert not failures, (
        f"{len(failures)} iterations failed: {failures!r}; "
        f"captured stderr: {captured.err!r}"
    )
    assert "Bad file descriptor" not in captured.err
