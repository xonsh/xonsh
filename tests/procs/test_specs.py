"""Tests the xonsh.procs.specs"""

import gc
import itertools
import os
import signal
import sys
import warnings
from subprocess import CalledProcessError, Popen

import pytest

from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import STDOUT_DISPATCHER, ProcProxy, ProcProxyThread
from xonsh.procs.specs import (
    DecoratorAlias,
    SpecAttrDecoratorAlias,
    SubprocSpec,
    _has_path_component,
    _run_command_pipeline,
    cmds_to_specs,
    get_script_subproc_command,
    run_subproc,
    safe_close,
)
from xonsh.pytest.tools import (
    ON_WINDOWS,
    VER_MAJOR_MINOR,
    skip_if_on_bsd,
    skip_if_on_windows,
)
from xonsh.tools import XonshError, chdir

# TODO: track down which pipeline + spec test is hanging CI
# Skip entire test file for Linux on Python 3.12
pytestmark = pytest.mark.skipif(
    not ON_WINDOWS and VER_MAJOR_MINOR == (3, 12),
    reason="Backgrounded test is hanging on CI on 3.12 only",
    allow_module_level=True,
)


def cmd_sig(sig):
    # ``sys.executable`` resolves to the running interpreter (e.g.
    # ``/usr/local/bin/python3.11``). A bare ``"python"`` would fail on
    # build environments that only ship versioned binaries — FreeBSD
    # ports / poudriere jails being the canonical example — turning every
    # test that uses this helper into a ``command not found``.
    return [
        sys.executable,
        "-c",
        f"import os, signal; os.kill(os.getpid(), signal.{sig})",
    ]


@skip_if_on_windows
def test_cmds_to_specs_thread_subproc(xession):
    env = xession.env
    cmds = [["pwd"]]

    def _check_cls(cmds, expected_cls):
        # `cmds_to_specs` opens pipe wrappers for captured specs that this
        # test never executes; close them so they don't leak as
        # `ResourceWarning: unclosed file`.
        specs = cmds_to_specs(cmds, captured="hiddenobject")
        try:
            assert specs[0].cls is expected_cls
        finally:
            for s in specs:
                s.close()

    # XONSH_CAPTURE_ALWAYS=False should disable interactive threaded subprocs
    env["XONSH_CAPTURE_ALWAYS"] = False
    env["THREAD_SUBPROCS"] = True
    _check_cls(cmds, Popen)

    # Now for the other situations
    env["XONSH_CAPTURE_ALWAYS"] = True

    # First check that threadable subprocs become threadable
    env["THREAD_SUBPROCS"] = True
    _check_cls(cmds, PopenThread)
    # turn off threading and check we use Popen
    env["THREAD_SUBPROCS"] = False
    _check_cls(cmds, Popen)

    # now check the threadbility of callable aliases
    cmds = [[lambda: "Keras Selyrian"]]
    # check that threadable alias become threadable
    env["THREAD_SUBPROCS"] = True
    _check_cls(cmds, ProcProxyThread)
    # turn off threading and check we use ProcProxy
    env["THREAD_SUBPROCS"] = False
    _check_cls(cmds, ProcProxy)


@pytest.mark.parametrize("thread_subprocs", [True, False])
def test_cmds_to_specs_capture_stdout_not_stderr(thread_subprocs, xonsh_session):
    env = xonsh_session.env
    cmds = (["ls", "/root"],)

    env["THREAD_SUBPROCS"] = thread_subprocs

    specs = cmds_to_specs(cmds, captured="stdout")
    try:
        assert specs[0].stdout is not None
        assert specs[0].stderr is None
    finally:
        # The spec is never executed here; release its pipe wrappers so they
        # don't surface as `ResourceWarning: unclosed file` at GC time.
        for s in specs:
            s.close()


@skip_if_on_windows
@pytest.mark.parametrize("captured", ["stdout", "object", "hiddenobject"])
def test_subproc_spec_close_releases_pipe_wrappers(captured, xession):
    """Regression: SubprocSpec.close() must release every pipe wrapper.

    `cmds_to_specs` opens pipe wrappers via `PipeChannel.open_writer/
    open_reader` (with `closefd=False`) for any captured spec. When the
    spec is never executed, GC reaping the wrappers triggers
    `ResourceWarning: unclosed file` (delivered via sys.unraisablehook,
    invisible to ordinary warning filters). `SubprocSpec.close()` must
    drop them deterministically.
    """
    xession.env["THREAD_SUBPROCS"] = True
    if captured == "hiddenobject":
        xession.env["XONSH_CAPTURE_ALWAYS"] = True

    # Reap any garbage left over from earlier tests so its ResourceWarnings
    # don't leak into our tracking window.
    gc.collect()

    unraisable = []
    orig_hook = sys.unraisablehook
    sys.unraisablehook = lambda args: unraisable.append(args)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)

            specs = cmds_to_specs([["pwd"]], captured=captured)
            assert specs[0].pipe_channels, "test premise: spec must own pipes"
            for s in specs:
                s.close()
            del specs
            gc.collect()
    finally:
        sys.unraisablehook = orig_hook

    leaks = [
        u
        for u in unraisable
        if isinstance(u.exc_value, ResourceWarning)
        and "unclosed file" in str(u.exc_value)
    ]
    assert not leaks, f"pipe wrappers leaked: {[str(u.exc_value) for u in leaks]}"


@skip_if_on_windows
@pytest.mark.parametrize("pipe", (True, False))
@pytest.mark.parametrize("alias_type", (None, "func", "exec", "simple"))
@pytest.mark.parametrize(
    "thread_subprocs, capture_always", list(itertools.product((True, False), repeat=2))
)
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_capture_always(
    capfd, thread_subprocs, capture_always, alias_type, pipe, monkeypatch, xonsh_session
):
    if not thread_subprocs and alias_type in ["func", "exec"]:
        if pipe:
            return pytest.skip("https://github.com/xonsh/xonsh/issues/4443")
        else:
            return pytest.skip("https://github.com/xonsh/xonsh/issues/4444")

    env = xonsh_session.env
    exp = "HELLO\nBYE\n"
    cmds = [["echo", "-n", exp]]
    if pipe:
        exp = exp.splitlines()[1]  # second line
        cmds += ["|", ["grep", "--color=never", exp.strip()]]

    if alias_type:
        first_cmd = cmds[0]
        # Enable capfd for function aliases:
        monkeypatch.setattr(STDOUT_DISPATCHER, "default", sys.stdout)
        if alias_type == "func":
            xonsh_session.aliases["tst"] = lambda: (
                run_subproc([first_cmd], "hiddenobject") and None
            )  # Don't return a value
        elif alias_type == "exec":
            first_cmd = " ".join(repr(arg) for arg in first_cmd)
            xonsh_session.aliases["tst"] = f"![{first_cmd}]"
        else:
            # alias_type == "simple"
            xonsh_session.aliases["tst"] = first_cmd

        cmds[0] = ["tst"]

    env["THREAD_SUBPROCS"] = thread_subprocs
    env["XONSH_CAPTURE_ALWAYS"] = capture_always

    hidden = run_subproc(cmds, "hiddenobject")  # ![]
    # Check that interactive subprocs are always printed
    assert exp in capfd.readouterr().out

    if capture_always and thread_subprocs:
        # Check that the interactive output was captured
        assert hidden.out == exp
    else:
        # without THREAD_SUBPROCS capturing in ![] isn't possible
        assert not hidden.out

    # Explicitly captured commands are always captured
    hidden = run_subproc(cmds, "object")  # !()
    hidden.end()
    assert exp not in capfd.readouterr().out
    assert hidden.out == exp

    output = run_subproc(cmds, "stdout")  # $()
    assert exp not in capfd.readouterr().out
    assert output == exp

    # Explicitly non-captured commands are never captured (/always printed)
    run_subproc(cmds, captured=False)  # $[]
    assert exp in capfd.readouterr().out


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_callias_captured_redirect(xonsh_session, tmpdir):
    @xonsh_session.aliases.register("a")
    def _a(a, i, o, e):
        print("print_stdout")
        xonsh_session.subproc_captured_stdout(["echo", "cap_stdout"])
        xonsh_session.subproc_captured_object(["echo", "cap_object"])
        xonsh_session.subproc_captured_hiddenobject(["echo", "hiddenobject"])
        xonsh_session.subproc_uncaptured(["echo", "uncaptured"])
        print("print_error", file=e)

    f = tmpdir / "capture.txt"
    cmd = (["a", (">", str(f))],)
    specs = cmds_to_specs(cmd, captured="hiddenobject")
    _run_command_pipeline(specs, cmd).end()
    assert f.read_text(encoding="utf-8") == "print_stdout\nhiddenobject\n"


@skip_if_on_windows
@pytest.mark.parametrize("captured", ["stdout", "object"])
@pytest.mark.parametrize("interactive", [True, False])
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_interrupted_process_returncode(xonsh_session, captured, interactive):
    xonsh_session.env["XONSH_INTERACTIVE"] = interactive
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False
    cmd = [cmd_sig("SIGINT")]
    specs = cmds_to_specs(cmd, captured="stdout")
    (p := _run_command_pipeline(specs, cmd)).end()
    assert p.proc.returncode == -signal.SIGINT


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_proc_raise_subproc_error(xonsh_session):
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False

    specs = cmds_to_specs(cmd := [["ls"]], captured="stdout")
    specs[-1].raise_subproc_error = True
    exception = None
    try:
        (p := _run_command_pipeline(specs, cmd)).end()
        assert p.proc.returncode == 0
    except Exception as e:
        exception = e
    assert exception is None

    specs = cmds_to_specs(cmd := [["ls", "nofile"]], captured="stdout")
    specs[-1].raise_subproc_error = False
    exception = None
    try:
        (p := _run_command_pipeline(specs, cmd)).end()
        assert p.proc.returncode > 0
    except Exception as e:
        exception = e
    assert exception is None

    specs = cmds_to_specs(cmd := [["ls", "nofile"]], captured="stdout")
    specs[-1].raise_subproc_error = True
    exception = None
    try:
        (p := _run_command_pipeline(specs, cmd)).end()
    except Exception as e:
        assert p.proc.returncode > 0
        exception = e
    assert isinstance(exception, CalledProcessError)

    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    specs = cmds_to_specs(cmd := [["ls", "nofile"]], captured="stdout")
    exception = None
    try:
        (p := _run_command_pipeline(specs, cmd)).end()
    except Exception as e:
        assert p.proc.returncode > 0
        exception = e
    assert isinstance(exception, CalledProcessError)


def _check_suspended_pipeline(xonsh_session, suspended_pipeline):
    xonsh_session.env["XONSH_INTERACTIVE"] = True
    specs = cmds_to_specs(suspended_pipeline, captured="object")
    p = _run_command_pipeline(specs, suspended_pipeline)
    # The child needs time to actually receive its self-sent stop signal
    # *and* to let xonsh's reader thread call ``waitpid(WUNTRACED)`` at
    # least once — otherwise the child races through SIGSTOP → SIGCONT
    # → exit before xonsh observes ``WIFSTOPPED`` and ``p.suspended``
    # never gets set. 100 ms is comfortably above the reader's polling
    # cadence; this was tight enough on FreeBSD 16-CURRENT to flake
    # roughly half the runs without the wait.
    import time

    time.sleep(0.1)
    p.proc.send_signal(signal.SIGCONT)
    p.end()
    assert p.suspended


@skip_if_on_windows
@skip_if_on_bsd
@pytest.mark.parametrize(
    "suspended_pipeline",
    [
        [cmd_sig("SIGTTIN")],
        [["echo", "1"], "|", cmd_sig("SIGTTIN")],
        [["echo", "1"], "|", cmd_sig("SIGTTIN"), "|", ["head"]],
    ],
)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_specs_with_suspended_captured_process_pipeline_sigttin(
    xonsh_session, suspended_pipeline
):
    """Realistic case: child sends itself SIGTTIN (the "background process
    tried to read from tty" signal), gets stopped, parent resumes via SIGCONT.

    Skipped on BSD: FreeBSD's kernel silently drops a self-sent SIGTTIN /
    SIGTTOU / SIGTSTP even when the child's process group has ``pg_jobc > 0``
    (i.e. the PG is *not* orphaned per POSIX), so the child never enters the
    stopped state. Externally-sent SIGTTIN does work on FreeBSD, and SIGSTOP
    works in either direction — see the ``_sigstop`` companion test for
    portable coverage.
    """
    _check_suspended_pipeline(xonsh_session, suspended_pipeline)


@skip_if_on_windows
@pytest.mark.parametrize(
    "suspended_pipeline",
    [
        [cmd_sig("SIGSTOP")],
        [["echo", "1"], "|", cmd_sig("SIGSTOP")],
        [["echo", "1"], "|", cmd_sig("SIGSTOP"), "|", ["head"]],
    ],
)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_specs_with_suspended_captured_process_pipeline_sigstop(
    xonsh_session, suspended_pipeline
):
    """Portable variant: SIGSTOP is uncatchable and stops the child on every
    POSIX kernel xonsh supports. The xonsh code path under test is the same —
    detection of ``WIFSTOPPED`` via ``waitpid`` — so this is what guarantees
    suspended-pipeline detection is exercised on FreeBSD too.
    """
    _check_suspended_pipeline(xonsh_session, suspended_pipeline)


@skip_if_on_windows
@pytest.mark.parametrize(
    "cmds, exp_stream_lines, exp_list_lines",
    [
        ([["echo", "-n", "1"]], "1", ["1"]),
        ([["echo", "-n", "1\n"]], "1", ["1"]),
        ([["echo", "-n", "1\n2\n3\n"]], "1\n2\n3\n", ["1", "2", "3"]),
        ([["echo", "-n", "1\r\n2\r3\r\n"]], "1\n2\n3\n", ["1", "2", "3"]),
        ([["echo", "-n", "1\n2\n3"]], "1\n2\n3", ["1", "2", "3"]),
        ([["echo", "-n", "1\n2 3"]], "1\n2 3", ["1", "2 3"]),
    ],
)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_subproc_output_format(cmds, exp_stream_lines, exp_list_lines, xonsh_session):
    xonsh_session.env["XONSH_SUBPROC_OUTPUT_FORMAT"] = "stream_lines"
    output = run_subproc(cmds, "stdout")
    assert output == exp_stream_lines

    xonsh_session.env["XONSH_SUBPROC_OUTPUT_FORMAT"] = "list_lines"
    output = run_subproc(cmds, "stdout")
    assert output == exp_list_lines


@skip_if_on_windows
@pytest.mark.parametrize(
    "captured, exp_is_none",
    [
        ("object", False),
        ("stdout", True),
        ("hiddenobject", False),
        (False, True),
    ],
)
def test_run_subproc_background(captured, exp_is_none, xonsh_session):
    # Suppress job notification print from add_job()
    xonsh_session.env["XONSH_INTERACTIVE"] = False
    cmds = (["echo", "hello"], "&")
    return_val = run_subproc(cmds, captured)
    assert (return_val is None) == exp_is_none


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "wrap_boolop",
    [False, True],
    ids=["helper_only", "with_boolop_wrap"],
)
def test_subproc_uncaptured_background_does_not_block(wrap_boolop, xonsh_session):
    # Background jobs must return immediately even when
    # $XONSH_SUBPROC_RAISE_ERROR=True. The error-check helpers used
    # to read the blocking `returncode` property on the still-running
    # pipeline, stalling the shell until the child exited.
    import time as _time

    from xonsh.built_ins import XSH, subproc_check_boolop, subproc_uncaptured

    xonsh_session.env["XONSH_INTERACTIVE"] = False
    xonsh_session.env["XONSH_SUBPROC_RAISE_ERROR"] = True

    long_running = [sys.executable, "-c", "import time; time.sleep(30)"]
    cp = None
    try:
        t0 = _time.monotonic()
        result = subproc_uncaptured(long_running, "&")
        if wrap_boolop:
            result = subproc_check_boolop(result)
        elapsed = _time.monotonic() - t0
        assert result is None
        assert elapsed < 5, f"background subproc helper blocked for {elapsed:.1f}s"
        cp = XSH.lastcmd
    finally:
        proc = getattr(cp, "proc", None) if cp is not None else None
        if proc is not None and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass


def test_spec_decorator_alias_alone(xession):
    xession.aliases["xunthread"] = SpecAttrDecoratorAlias(
        {"threadable": False, "force_threadable": False}
    )

    cmds = [["xunthread"]]
    spec = cmds_to_specs(cmds, captured="object")[-1]

    assert spec.cmd == []
    assert spec.alias_name == "xunthread"


def test_spec_decorator_alias(xession):
    xession.aliases["xunthread"] = SpecAttrDecoratorAlias(
        {"threadable": False, "force_threadable": False}
    )

    cmds = [["xunthread", "echo", "arg0", "arg1"]]
    spec = cmds_to_specs(cmds, captured="object")[-1]

    assert spec.cmd == ["echo", "arg0", "arg1"]
    assert spec.threadable is False
    assert spec.force_threadable is False


def test_spec_decorator_alias_tree(xession):
    xession.aliases["xthread"] = SpecAttrDecoratorAlias(
        {"threadable": True, "force_threadable": True}
    )
    xession.aliases["xunthread"] = SpecAttrDecoratorAlias(
        {"threadable": False, "force_threadable": False}
    )

    xession.aliases["foreground"] = "xthread midground f0 f1"
    xession.aliases["midground"] = "ground m0 m1"
    xession.aliases["ground"] = "xthread underground g0 g1"
    xession.aliases["underground"] = "xunthread echo u0 u1"

    cmds = [
        ["foreground"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]

    assert spec.cmd == ["echo", "u0", "u1", "g0", "g1", "m0", "m1", "f0", "f1"]
    assert spec.alias_name == "foreground"
    assert spec.threadable is False
    assert spec.force_threadable is False


def test_spec_decorator_alias_multiple(xession):
    xession.aliases["@unthread"] = SpecAttrDecoratorAlias(
        {"threadable": False, "force_threadable": False}
    )
    xession.aliases["@dict"] = SpecAttrDecoratorAlias({"output_format": "list_lines"})

    cmds = [
        ["@unthread", "@dict", "echo", "1"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]

    assert spec.cmd == ["echo", "1"]
    assert spec.alias_name is None
    assert spec.threadable is False
    assert spec.force_threadable is False
    assert spec.output_format == "list_lines"


@skip_if_on_windows
def test_spec_decorator_alias_output_format(xession):
    class OutputLinesDecoratorAlias(DecoratorAlias):
        def decorate_spec(self, spec):
            spec.output_format = "list_lines"

    xession.aliases["xlines"] = OutputLinesDecoratorAlias()

    cmds = [["xlines", "echo", "1\n2\n3"]]
    specs = cmds_to_specs(cmds, captured="stdout")
    (p := _run_command_pipeline(specs, cmds)).end()
    assert p.output == ["1", "2", "3"]


@pytest.mark.parametrize("thread_subprocs", [False, True])
def test_callable_alias_cls(thread_subprocs, xession):
    class Cls:
        def __call__(self, *args, **kwargs):
            print(args, kwargs)

    obj = Cls()
    xession.aliases["tst"] = obj

    env = xession.env
    cmds = (["tst", "/root"],)

    env["THREAD_SUBPROCS"] = thread_subprocs

    spec = cmds_to_specs(cmds, captured="stdout")[0]
    proc = spec.run()
    assert proc.f == obj
    if hasattr(proc, "join"):
        proc.join()
    safe_close(spec.stdout)
    safe_close(spec.stderr)
    safe_close(spec.captured_stdout)
    safe_close(spec.captured_stderr)


def test_specs_resolve_args_list():
    spec = cmds_to_specs([["echo", ["1", "2", "3"]]], captured="stdout")[0]
    assert spec.cmd[-3:] == ["1", "2", "3"]


@pytest.mark.parametrize("captured", ["hiddenobject", False])
def test_procproxy_not_captured(xession, captured):
    xession.aliases["tst"] = lambda: 0
    cmds = (["tst", "/root"],)

    xession.env["THREAD_SUBPROCS"] = False
    specs = cmds_to_specs(cmds, captured)

    assert specs[0].cls is ProcProxy

    # neither stdout nor stderr should be captured
    assert specs[0].stdout is None
    assert specs[0].stderr is None


def test_on_command_not_found_fires(xession):
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    fired = False

    def my_handler(cmd, **kwargs):
        nonlocal fired
        assert cmd[0] == "xonshcommandnotfound"
        fired = True

    xession.builtins.events.on_command_not_found(my_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: 'xonshcommandnotfound'" in str(expected.value)
    assert fired


def test_on_command_not_found_doesnt_fire_in_non_interactive_mode(xession):
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=False,
        )
    )

    fired = False

    def my_handler(cmd, **kwargs):
        nonlocal fired
        assert cmd[0] == "xonshcommandnotfound"
        fired = True

    xession.builtins.events.on_command_not_found(my_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: 'xonshcommandnotfound'" in str(expected.value)
    assert not fired


def test_on_command_not_found_replacement(xession):
    """Test that returning a command from handler replaces the original."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def replacement_handler(cmd, **kwargs):
        if cmd[0] == "xonshcommandnotfound":
            if ON_WINDOWS:
                return ["cmd", "/c", "echo", "replaced"]
            return ["echo", "replaced"]
        return None

    xession.builtins.events.on_command_not_found(replacement_handler)
    # Use run_subproc to capture output and verify replacement executed
    out = run_subproc([["xonshcommandnotfound"]], captured="stdout")
    assert out.strip() == "replaced"


def test_on_command_not_found_no_replacement(xession):
    """Test that returning None still raises error."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def no_replacement_handler(cmd, **kwargs):
        return None  # Don't replace

    xession.builtins.events.on_command_not_found(no_replacement_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: 'xonshcommandnotfound'" in str(expected.value)


def test_on_command_not_found_invalid_replacement_ignored(xession):
    """Test that invalid replacements (non-list, empty) are ignored."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def invalid_replacement_handler(cmd, **kwargs):
        # Return invalid types that should be ignored
        return "not a list"  # Should be ignored

    xession.builtins.events.on_command_not_found(invalid_replacement_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    assert "command not found: 'xonshcommandnotfound'" in str(expected.value)


def test_on_command_not_found_fallback_on_bad_replacement(xession):
    """Test that if replacement command also doesn't exist, original error is shown."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def bad_replacement_handler(cmd, **kwargs):
        # Return a command that also doesn't exist
        return ["anotherfakecommand999"]

    xession.builtins.events.on_command_not_found(bad_replacement_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError) as expected:
        subproc.run()
    # Should show original error, not error about the replacement
    assert "command not found: 'xonshcommandnotfound'" in str(expected.value)


def test_on_command_not_found_dict_replacement_with_env(xession):
    """Test that returning a dict with cmd and env sets the subprocess environment."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def dict_handler(cmd, **kwargs):
        if cmd[0] == "xonshcommandnotfound":
            if ON_WINDOWS:
                return {
                    "cmd": ["cmd", "/c", "echo", "%XONSH_TEST_VAR%"],
                    "env": {"XONSH_TEST_VAR": "hello_from_env"},
                }
            return {
                "cmd": ["sh", "-c", "echo $XONSH_TEST_VAR"],
                "env": {"XONSH_TEST_VAR": "hello_from_env"},
            }
        return None

    xession.builtins.events.on_command_not_found(dict_handler)
    out = run_subproc([["xonshcommandnotfound"]], captured="stdout")
    assert "hello_from_env" in out.strip()


def test_on_command_not_found_dict_without_env(xession):
    """Test that returning a dict with only cmd (no env) works."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def dict_no_env_handler(cmd, **kwargs):
        if cmd[0] == "xonshcommandnotfound":
            if ON_WINDOWS:
                return {"cmd": ["cmd", "/c", "echo", "dict_no_env"]}
            return {"cmd": ["echo", "dict_no_env"]}
        return None

    xession.builtins.events.on_command_not_found(dict_no_env_handler)
    out = run_subproc([["xonshcommandnotfound"]], captured="stdout")
    assert out.strip() == "dict_no_env"


def test_on_command_not_found_dict_missing_cmd_ignored(xession):
    """Test that a dict without 'cmd' key is treated as invalid and ignored."""
    xession.env.update(
        dict(
            XONSH_INTERACTIVE=True,
        )
    )

    def bad_dict_handler(cmd, **kwargs):
        return {"env": {"FOO": "bar"}}  # no 'cmd' key

    xession.builtins.events.on_command_not_found(bad_dict_handler)
    subproc = SubprocSpec.build(["xonshcommandnotfound"])
    with pytest.raises(XonshError):
        subproc.run()


def test_redirect_to_substitution(tmpdir):
    file = str(tmpdir / "test_redirect_to_substitution.txt")
    s = SubprocSpec.build(
        # `echo hello > @('file')`
        ["echo", "hello", (">", [file])]
    )
    assert s.stdout.name == file
    s.stdout.close()


def test_partial_args_from_classmethod(xession):
    class Class:
        @classmethod
        def alias(cls, args, stdin, stdout):
            print("ok", file=stdout)
            return 0

    xession.aliases["alias_with_partial_args"] = Class.alias
    out = run_subproc([["alias_with_partial_args"]], captured="stdout")
    assert out == "ok"


def test_alias_return_command_alone(xession):
    @xession.aliases.register("wakka")
    @xession.aliases.return_command
    def _wakka(args):
        return ["echo"] + args

    cmds = [
        ["wakka"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == ["echo"]
    assert spec.alias_name == "wakka"


@pytest.mark.parametrize("ret", [None, 1, [], False])
def test_alias_return_command_wrong_return(xession, ret):
    @xession.aliases.register
    @xession.aliases.return_command
    def _nop():
        return ret

    with pytest.raises(ValueError):
        cmds_to_specs([["nop"]], captured="object")[-1]


def test_alias_return_command_alone_args(xession):
    @xession.aliases.register("wakka")
    @xession.aliases.return_command
    def _wakka(args):
        return ["echo", "e0", "e1"] + args

    cmds = [
        ["wakka", "0", "1"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == ["echo", "e0", "e1", "0", "1"]
    assert spec.alias_name == "wakka"


def test_alias_return_command_chain(xession):
    xession.aliases["foreground"] = "midground f0 f1"

    @xession.aliases.register("midground")
    @xession.aliases.return_command
    def _midground(args):
        return ["ground", "m0", "m1"] + args

    xession.aliases["ground"] = "background g0 g1"
    xession.aliases["background"] = "echo b0 b1"

    cmds = [
        ["foreground", "0", "1"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == [
        "echo",
        "b0",
        "b1",
        "g0",
        "g1",
        "m0",
        "m1",
        "f0",
        "f1",
        "0",
        "1",
    ]
    assert spec.alias_name == "foreground"


def test_alias_return_command_chain_decorators(xession):
    xession.aliases["foreground"] = "midground f0 f1"

    xession.aliases["xunthread"] = SpecAttrDecoratorAlias(
        {"threadable": False, "force_threadable": False}
    )

    @xession.aliases.register("midground")
    @xession.aliases.return_command
    def _midground(args):
        return ["ground", "m0", "m1"]

    xession.aliases["ground"] = "background g0 g1"
    xession.aliases["background"] = "xunthread echo b0 b1"

    cmds = [
        ["foreground", "0", "1"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == ["echo", "b0", "b1", "g0", "g1", "m0", "m1"]
    assert spec.alias_name == "foreground"
    assert spec.threadable is False


def test_alias_return_command_eval_inside(xession):
    xession.aliases["xthread"] = SpecAttrDecoratorAlias(
        {"threadable": True, "force_threadable": True}
    )

    @xession.aliases.register("xwrap")
    @xession.aliases.return_command
    def _midground(args, decorators=None):
        return [
            "wrapper",
            *xession.aliases.eval_alias(args, decorators=decorators),
        ]

    xession.aliases["cmd"] = "xthread echo 1"

    cmds = [
        ["xwrap", "cmd"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == ["wrapper", "echo", "1"]
    assert spec.alias_name == "xwrap"
    assert spec.threadable is True


def test_alias_env_overlay(xession):
    """env overlay shadows global env during alias, global writes persist."""
    xession.env["GLOBAL"] = "before"
    alias_env = {}
    with xession.env.swap(overlay=alias_env):
        xession.env["GLOBAL"] = "global_write"
        alias_env["GLOBAL"] = "overlay"
        assert xession.env["GLOBAL"] == "overlay"
    assert xession.env["GLOBAL"] == "global_write"


def test_return_command_alias_env_kwarg_is_body_only(xession):
    """The ``env=`` kwarg of a return_command alias is a live overlay
    active only during the function body. It does NOT become the returned
    command's env overlay, and it does NOT persist after the alias exits.
    To set env for the returned command, the alias must use dict-return.
    """
    captured = {}

    @xession.aliases.register("rca")
    @xession.aliases.return_command
    def _rca(args, env=None):
        env["BODY_ONLY"] = "yes"
        # While the body runs, the overlay is active. Read via
        # ``__getitem__`` / ``__contains__`` — those consult the overlay
        # stack (and so does the ``detype()`` path used for subprocess env).
        captured["during"] = xession.env["BODY_ONLY"]
        captured["in_env"] = "BODY_ONLY" in xession.env
        captured["detype"] = xession.env.detype().get("BODY_ONLY")
        xession.env["GLOBAL"] = "321"  # direct write persists after exit
        return ["echo", "ok"]

    spec = cmds_to_specs([["rca"]], captured="object")[-1]
    # Overlay was visible to every "normal" read path during the body
    assert captured["during"] == "yes"
    assert captured["in_env"] is True
    assert captured["detype"] == "yes"
    # Overlay does NOT leak to the returned command's env
    assert spec.env is None or "BODY_ONLY" not in (spec.env or {})
    # Overlay does NOT persist in the global env either
    assert "BODY_ONLY" not in xession.env
    # A direct write during the body persists normally
    assert xession.env["GLOBAL"] == "321"


def test_return_command_alias_dict_cmd_only(xession):
    """Dict return with only ``cmd`` is treated like a bare list return."""

    @xession.aliases.register("rcdc")
    @xession.aliases.return_command
    def _rcdc(args):
        return {"cmd": ["echo", "ok"] + args}

    spec = cmds_to_specs([["rcdc", "x"]], captured="object")[-1]
    assert spec.cmd == ["echo", "ok", "x"]
    # No env overlay was requested
    assert spec.env is None or "LOCAL" not in (spec.env or {})


def test_return_command_alias_dict_cmd_and_env(xession):
    """Dict return carries both ``cmd`` and ``env`` overlay in one go."""

    @xession.aliases.register("rcde")
    @xession.aliases.return_command
    def _rcde(args):
        return {"cmd": ["echo", "ok"], "env": {"LOCAL": "123", "FOO": "bar"}}

    spec = cmds_to_specs([["rcde"]], captured="object")[-1]
    assert spec.cmd == ["echo", "ok"]
    assert spec.env is not None
    assert spec.env.get("LOCAL") == "123"
    assert spec.env.get("FOO") == "bar"
    # env overlay must not leak into the global env
    assert "LOCAL" not in xession.env
    assert "FOO" not in xession.env


def test_return_command_alias_dict_env_independent_of_kwarg_env(xession):
    """Dict-return ``"env"`` and the ``env=`` kwarg are independent: the
    kwarg env is only a body-scoped overlay, and the dict env is the only
    source of the returned command's env overlay."""

    @xession.aliases.register("rcme")
    @xession.aliases.return_command
    def _rcme(args, env=None):
        # These only affect the function body, not the returned command.
        env["BODY_ONLY_A"] = "body_a"
        env["BODY_ONLY_B"] = "body_b"
        return {
            "cmd": ["echo", "ok"],
            "env": {"RETURNED": "returned_value"},
        }

    spec = cmds_to_specs([["rcme"]], captured="object")[-1]
    assert spec.cmd == ["echo", "ok"]
    assert spec.env is not None
    # Dict-return env is on the returned command
    assert spec.env.get("RETURNED") == "returned_value"
    # Kwarg env does NOT flow through
    assert "BODY_ONLY_A" not in spec.env
    assert "BODY_ONLY_B" not in spec.env


@pytest.mark.parametrize(
    "bad",
    [
        {},  # no "cmd"
        {"cmd": []},  # empty cmd
        {"cmd": None},  # missing cmd
        {"cmd": "echo"},  # cmd not a list
        {"cmd": ["echo"], "env": "X=1"},  # env not a dict
        {"cmd": ["echo"], "env": ["X", "1"]},  # env not a dict
    ],
)
def test_return_command_alias_dict_wrong_return(xession, bad):
    """Malformed dict returns raise ValueError."""

    @xession.aliases.register("rcwr")
    @xession.aliases.return_command
    def _rcwr(args):
        return bad

    with pytest.raises(ValueError):
        cmds_to_specs([["rcwr"]], captured="object")[-1]


def test_return_command_alias_dict_env_through_string_alias_chain(xession):
    """Chain: a plain string alias points to a return_command alias that
    dict-returns an env overlay. The overlay must still reach the returned
    command's spec.env (propagated through eval_alias via env_out).

    Also verifies that the chain's positional args are concatenated with
    the user's call-site args when both reach the return_command function.
    """
    seen_args = []

    @xession.aliases.register("rca")
    @xession.aliases.return_command
    def _rca(args):
        seen_args.append(list(args))
        return {
            "cmd": ["echo", "ok"] + args,
            "env": {"VIA_CHAIN": "yes", "EXTRA": "1"},
        }

    xession.aliases["hlp"] = "rca X1 X2"

    spec = cmds_to_specs([["hlp", "Y1", "Y2"]], captured="object")[-1]

    # args from the chain ("X1 X2") come first, then args from the user call.
    assert seen_args == [["X1", "X2", "Y1", "Y2"]]
    assert spec.cmd == ["echo", "ok", "X1", "X2", "Y1", "Y2"]

    # Dict-return env survived the string-alias chain and lives on spec.env.
    assert spec.env is not None
    assert spec.env.get("VIA_CHAIN") == "yes"
    assert spec.env.get("EXTRA") == "1"
    # And did not leak into the global env.
    assert "VIA_CHAIN" not in xession.env
    assert "EXTRA" not in xession.env


def test_auto_cd(xession, tmpdir):
    xession.aliases["cd"] = lambda: "some_cd_alias"
    dir = str(tmpdir)
    with xession.env.swap(AUTO_CD=True):
        spec = cmds_to_specs([[dir]], captured="object")[-1]
    assert spec.alias.__name__ == "cd"
    assert spec.cmd[0] == dir


@skip_if_on_windows
@pytest.mark.parametrize(
    "inp,exp",
    [
        ["echo command", ["xonsh", "{file}", "--arg", "1"]],
        ["#!/bin/bash", ["/bin/bash", "{file}", "--arg", "1"]],
        ["#!/bin/bash\necho 1", ["/bin/bash", "{file}", "--arg", "1"]],
        ["#!/bin/bash\n\necho 1", ["/bin/bash", "{file}", "--arg", "1"]],
        ["#!/bin/bash \\\n-i", ["/bin/bash", "-i", "{file}", "--arg", "1"]],
        ["#!/bin/bash \\\n-i\necho 1", ["/bin/bash", "-i", "{file}", "--arg", "1"]],
        [
            "#!/bin/bash \\\n-i \\\n-i \necho 1",
            ["/bin/bash", "-i", "-i", "{file}", "--arg", "1"],
        ],
    ],
)
def test_get_script_subproc_command_shebang(tmpdir, inp, exp):
    file = tmpdir / "script.sh"
    file_str = str(file)
    file.write_text(inp, encoding="utf-8")
    file.chmod(0o755)
    cmd = get_script_subproc_command(file_str, ["--arg", "1"])
    assert [c if c != file_str else "{file}" for c in cmd] == exp


def test_redirect_without_left_part(tmpdir):
    file = str(tmpdir / "test_redirect_without_left_part.txt")
    with pytest.raises(XonshError) as expected:
        SubprocSpec.build([(">", file)])
    assert "subprocess mode: command is empty" in str(expected.value)


# -- a>p / e>p pipe-redirects ------------------------------------------------

import subprocess as _subprocess  # noqa: E402

from xonsh.procs.specs import _PIPE_ALL, _PIPE_ERR, _redirect_streams  # noqa: E402


@pytest.mark.parametrize("op", ["a>p", "all>p"])
def test_a2p_redirect_streams_returns_sentinel(op):
    stdin, stdout, stderr = _redirect_streams(op)
    assert stdin is None
    assert stdout is _PIPE_ALL
    assert stderr is _subprocess.STDOUT


@pytest.mark.parametrize("op", ["e>p", "err>p", "2>p"])
def test_e2p_redirect_streams_returns_sentinel(op):
    stdin, stdout, stderr = _redirect_streams(op)
    assert stdin is None
    assert stdout is None
    assert stderr is _PIPE_ERR


@skip_if_on_windows
def test_a2p_pipes_both_streams_to_next_spec(xession):
    cmds = [["echo", "hi", ("a>p",)], "|", ["cat"]]
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert len(specs) == 2
    # upstream: stdout wired to pipe write fd, stderr merged via STDOUT flag
    assert isinstance(specs[0].stdout, int)
    assert specs[0].stderr is _subprocess.STDOUT
    # downstream: stdin reads from pipe
    assert isinstance(specs[1].stdin, int)
    # sentinel was replaced
    assert specs[0]._stdout is not _PIPE_ALL


@skip_if_on_windows
def test_e2p_without_stdout_redirect_pipes_both_streams(xession):
    """`cmd e>p | next` — pipe still carries stdout by default, plus stderr."""
    cmds = [["echo", "hi", ("e>p",)], "|", ["cat"]]
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert len(specs) == 2
    assert isinstance(specs[0].stdout, int)
    assert isinstance(specs[0].stderr, int)
    assert specs[0].stdout == specs[0].stderr  # same pipe write fd
    assert isinstance(specs[1].stdin, int)
    assert specs[0]._stderr is not _PIPE_ERR


@skip_if_on_windows
def test_e2p_with_stdout_redirect_preserves_file(xession, tmpdir):
    """`cmd o> file e>p | grep` — stdout to file, stderr through pipe."""
    outfile = str(tmpdir / "out.txt")
    cmds = [["echo", "hi", ("o>", outfile), ("e>p",)], "|", ["cat"]]
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    # stdout is a file object, stderr is the pipe fd
    assert getattr(specs[0].stdout, "name", None) == outfile
    assert isinstance(specs[0].stderr, int)
    specs[0].stdout.close()


@pytest.mark.parametrize("op", ["a>p", "e>p"])
def test_pipe_redirect_without_pipe_errors(xession, op):
    cmds = [["echo", "hi", (op,)]]
    with pytest.raises(XonshError, match=r"requires a following pipe"):
        cmds_to_specs(cmds, captured="hiddenobject")


def test_a2p_conflict_with_o_redirect_errors(xession, tmpdir):
    outfile = str(tmpdir / "conflict.txt")
    cmds = [["echo", "hi", ("a>p",), ("o>", outfile)], "|", ["cat"]]
    with pytest.raises(XonshError, match="Multiple redirections for stdout"):
        cmds_to_specs(cmds, captured="hiddenobject")


def test_e2p_conflict_with_e_redirect_errors(xession, tmpdir):
    errfile = str(tmpdir / "conflict.txt")
    cmds = [["echo", "hi", ("e>p",), ("e>", errfile)], "|", ["cat"]]
    with pytest.raises(XonshError, match="Multiple redirections for stderr"):
        cmds_to_specs(cmds, captured="hiddenobject")


def test_resolve_executable_commands_updates_binary_loc(tmpdir, xession):
    """After resolve_executable_commands wraps a script with an interpreter,
    binary_loc must point to the interpreter, not the script.
    Otherwise _run_binary (PR #4077) would try to launch the script directly
    via CreateProcess on Windows, causing WinError 193."""
    script = tmpdir / "test_script.xsh"
    script.write_text("echo hello", encoding="utf-8")
    if not ON_WINDOWS:
        script.chmod(0o755)
    spec = SubprocSpec.build([str(script)])
    # The command should be wrapped with an interpreter (python -m xonsh.main
    # on Windows, or xonsh on POSIX)
    assert spec.cmd[0] != str(script), "script should be wrapped with interpreter"
    # binary_loc must match the interpreter, not the original script
    if spec.binary_loc is not None:
        assert not spec.binary_loc.endswith(".xsh"), (
            f"binary_loc should point to interpreter, not script: {spec.binary_loc}"
        )


def test_has_path_component():
    """_has_path_component correctly distinguishes bare names from paths."""
    # Bare names — no path component
    assert not _has_path_component("ls")
    assert not _has_path_component("ls.exe")
    assert not _has_path_component("script.xsh")
    assert not _has_path_component("python")

    # Forward-slash paths (work on all platforms)
    assert _has_path_component("./script.sh")
    assert _has_path_component("../script.sh")
    assert _has_path_component("subdir/script.sh")
    assert _has_path_component("/usr/bin/ls")

    if ON_WINDOWS:
        assert _has_path_component(".\\script.exe")
        assert _has_path_component("..\\script.exe")
        assert _has_path_component("C:\\Windows\\cmd.exe")
        assert _has_path_component("subdir\\script.exe")


def test_bare_script_in_cwd_not_detected(tmpdir, xession):
    """Typing a bare script name that exists in CWD should NOT activate
    script detection.  The user must use an explicit path prefix
    (e.g. ./script.xsh) to run scripts from the current directory,
    matching POSIX shell behaviour."""
    script = tmpdir / "my_script.xsh"
    script.write_text("echo hello", encoding="utf-8")
    if not ON_WINDOWS:
        script.chmod(0o755)

    with chdir(str(tmpdir)):
        spec = SubprocSpec.build(["my_script.xsh"])
        # Script detection must NOT wrap the bare name with an interpreter
        assert spec.cmd[0] == "my_script.xsh", (
            "bare script name in CWD should not be resolved"
        )
        assert spec.binary_loc is None


def test_explicit_path_script_in_cwd_detected(tmpdir, xession):
    """Scripts referenced with an explicit path (./script.xsh) should
    still be detected and wrapped with an interpreter."""
    script = tmpdir / "my_script.xsh"
    script.write_text("echo hello", encoding="utf-8")
    if not ON_WINDOWS:
        script.chmod(0o755)

    sep = os.path.sep
    with chdir(str(tmpdir)):
        spec = SubprocSpec.build([f".{sep}my_script.xsh"])
        # Script detection MUST activate for explicit paths
        assert spec.cmd[0] != f".{sep}my_script.xsh", (
            "script with explicit path prefix should be wrapped with interpreter"
        )
