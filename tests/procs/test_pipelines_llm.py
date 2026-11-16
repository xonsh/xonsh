"""LLM-generated tests for ``xonsh.procs.pipelines``."""

import hashlib
import json
import os
import signal
import subprocess
import sys

import pytest

from xonsh.procs.pipelines import CommandPipeline
from xonsh.pytest.tools import skip_if_on_windows


@skip_if_on_windows
def test_returncode_finalizes_unreaped_proc(xonsh_session):
    """Regression for #6456: if ``tee_stdout`` bails before reaping
    (intermittent under load), ``end()`` leaves ``proc.returncode``
    unset.  ``CommandPipeline.returncode`` must still produce a
    definite int — not ``None`` — so the raise-check helpers don't
    conflate "undetermined" with "succeeded".

    Use a successful ``!(true)`` as the carrier pipeline (so the test
    is independent of ``$XONSH_SUBPROC_CMD_RAISE_ERROR``, which the
    in-CI ``run-tests.xsh`` enables) and inject the bug state by
    swapping ``pipeline.proc`` for one whose ``returncode`` is ``None``
    until ``poll()`` is called.
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()
    assert pipeline.proc.returncode == 0  # sanity

    real_rc = 7

    class _UnreapedProc:
        returncode = None

        def poll(self):
            self.returncode = real_rc
            return real_rc

    pipeline.proc = _UnreapedProc()
    assert pipeline.returncode == real_rc


@skip_if_on_windows
def test_returncode_stays_none_when_proc_still_alive(xonsh_session):
    """The poll-based fallback added for #6456 must not block: a
    still-alive proc keeps ``returncode`` at ``None`` so suspended /
    background pipelines still report "undetermined" to the
    raise-checks (which intentionally skip on ``None``).
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()
    assert pipeline.proc.returncode == 0

    class _AliveProc:
        returncode = None

        def poll(self):
            return None  # proc still running

    pipeline.proc = _AliveProc()
    assert pipeline.returncode is None


@skip_if_on_windows
def test_returncode_poll_failure_trace(xonsh_session, monkeypatch, capsys):
    """When ``$XONSH_SUBPROC_TRACE`` is enabled, a failing ``poll()`` in
    the #6456 fallback must surface its exception on stderr instead of
    silently swallowing it — so that the rare "proc disappeared" path
    is debuggable.  With trace off, the swallow stays silent.
    """
    pipeline: CommandPipeline = xonsh_session.execer.eval("!(true)")
    pipeline.end()

    class _PollFails:
        returncode = None

        def poll(self):
            raise RuntimeError("simulated poll failure")

    pipeline.proc = _PollFails()

    # Trace off — silent swallow, returncode is None.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_TRACE", 0)
    assert pipeline.returncode is None
    assert "simulated poll failure" not in capsys.readouterr().err

    # Trace on — exception surfaces on stderr; returncode is still None.
    monkeypatch.setitem(xonsh_session.env, "XONSH_SUBPROC_TRACE", 1)
    assert pipeline.returncode is None
    assert "simulated poll failure" in capsys.readouterr().err


@pytest.mark.parametrize(
    "statuses", [(7, 0), (7, 0, 0), (0, 9, 0), (0, 0), (7, 9, 0), (7, 9, 11), (0, 11)]
)
@pytest.mark.parametrize("cmd_raise", [False, True])
@pytest.mark.parametrize("form", ["bare", "bracket"])
@skip_if_on_windows
def test_completed_upstream_failure_native(tmp_path, statuses, form, cmd_raise):
    """EOF orders real children; the exception identifies the failed executable."""
    child = tmp_path / "stage.py"
    child.write_text(
        "import sys, os, json, pathlib\n"
        "i=int(sys.argv[1]); rc=int(sys.argv[2])\n"
        "data=sys.stdin.read() if i else 'payload\\n'\n"
        "pathlib.Path(sys.argv[3]).write_text(json.dumps({'pid':os.getpid()}))\n"
        "print(data, end='', flush=True)\n"
        "print('stderr-'+str(i), file=sys.stderr, flush=True)\n"
        "sys.exit(rc)\n"
    )
    argv = [
        [sys.executable, str(child), str(i), str(rc), str(tmp_path / f"{i}.json")]
        for i, rc in enumerate(statuses)
    ]
    commands = ["@( " + repr(args) + " )" for args in argv]
    pipeline = " | ".join(commands)
    if form == "bracket":
        pipeline = "$[" + pipeline + "]"
    failed = (
        len(statuses) - 1
        if statuses[-1]
        else next((i for i, rc in enumerate(statuses) if rc), None)
    )
    source = (
        "import subprocess, json\n"
        "$XONSH_SUBPROC_RAISE_ERROR = False\n"
        f"$XONSH_SUBPROC_CMD_RAISE_ERROR = {cmd_raise}\n"
        "try:\n    " + pipeline + "\n"
        "    print('FOLLOWING_STATEMENT')\n"
        "except subprocess.CalledProcessError as e:\n"
        "    print('ERROR:' + json.dumps([e.returncode, e.cmd]))\n"
        "p = __xonsh__.lastcmd\n"
        "print('STATE:' + json.dumps([p.returncode, p.pipestatus, bool(p), [s.is_proxy for s in p.specs]]))\n"
    )
    script = tmp_path / "probe.xsh"
    script.write_text(source)
    proc = subprocess.Popen(
        [sys.executable, "-m", "xonsh", "--no-rc", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=20)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
    (tmp_path / "result.json").write_text(
        json.dumps(
            {
                "outer_argv": proc.args,
                "exit": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
                "stage_argv": argv,
            }
        )
    )
    assert proc.returncode == 0, stderr.decode()
    lines = stdout.decode().splitlines()
    errors = [json.loads(line[6:]) for line in lines if line.startswith("ERROR:")]
    assert errors == (
        [[statuses[failed], argv[failed]]] if cmd_raise and failed is not None else []
    )
    assert ("FOLLOWING_STATEMENT" in lines) == (not cmd_raise or failed is None)
    state = next(json.loads(line[6:]) for line in lines if line.startswith("STATE:"))
    assert state == [
        statuses[-1],
        list(statuses),
        statuses[-1] == 0,
        [False] * len(statuses),
    ]
    assert "payload" in lines
    assert all(f"stderr-{i}" in stderr.decode() for i in range(len(statuses)))
    pids = [
        json.loads((tmp_path / f"{i}.json").read_text())["pid"]
        for i in range(len(statuses))
    ]
    assert len(set(pids)) == len(statuses)


@pytest.fixture
def completed_pipeline(xonsh_session, monkeypatch):
    """An ended pipeline for deterministic unknown-status and policy guards."""
    from types import SimpleNamespace

    def make(statuses=(7, 9, 0), policies=(None, None, None)):
        pipeline = object.__new__(CommandPipeline)
        pipeline.specs = [
            SimpleNamespace(
                args=[f"stage-{i}"],
                raise_subproc_error=policy,
                background=False,
                in_boolop=False,
            )
            for i, policy in enumerate(policies)
        ]
        pipeline.procs = [SimpleNamespace(returncode=rc) for rc in statuses]
        pipeline.spec = pipeline.specs[-1]
        pipeline.proc = pipeline.procs[-1]
        pipeline.captured = "hiddenobject"
        pipeline.suspended = False
        pipeline.ended = True
        pipeline._output = "retained output"
        restored = []
        monkeypatch.setattr(pipeline, "_return_terminal", lambda: restored.append(True))
        return pipeline, restored

    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    return make


@pytest.mark.parametrize("policy", [True, False, None, "fallback"])
@pytest.mark.parametrize("callable_policy", [False, True])
@pytest.mark.parametrize("terminal_ignore", [False, True])
def test_upstream_stage_policy(
    xonsh_session, capfd, policy, callable_policy, terminal_ignore
):
    from xonsh.procs.specs import SpecAttrDecoratorAlias, run_subproc

    calls = []

    def callback(spec, pipeline):
        calls.append((spec, pipeline))
        return policy

    def successful_policy(*args):
        pytest.fail("successful terminal policy was evaluated")

    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    xonsh_session.aliases["@first"] = SpecAttrDecoratorAlias(
        {"raise_subproc_error": callback if callable_policy else policy}
    )
    xonsh_session.aliases["@last"] = SpecAttrDecoratorAlias(
        {"raise_subproc_error": False if terminal_ignore else successful_policy}
    )
    first = [sys.executable, "-c", "import sys; print('payload'); sys.exit(7)"]
    middle = [
        sys.executable,
        "-c",
        "import sys; print(sys.stdin.read(), end=''); sys.exit(9)",
    ]
    last = [sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"]
    with pytest.raises(subprocess.CalledProcessError) as exc:
        run_subproc(
            [["@first", *first], "|", middle, "|", ["@last", *last]], "hiddenobject"
        )
    pipeline = xonsh_session.lastcmd
    expected = 1 if policy is False else 0
    assert (exc.value.returncode, exc.value.cmd, exc.value.output) == (
        [7, 9][expected],
        pipeline.specs[expected].args,
        pipeline.output,
    )
    assert "payload" in capfd.readouterr().out
    assert calls == ([(pipeline.specs[0], pipeline)] if callable_policy else [])
    assert (pipeline.returncode, pipeline.pipestatus, bool(pipeline)) == (
        0,
        [7, 9, 0],
        True,
    )
    assert all(not spec.is_proxy for spec in pipeline.specs)
    assert len({proc.pid for proc in pipeline.procs}) == 3
    pipeline.end()
    assert calls == ([(pipeline.specs[0], pipeline)] if callable_policy else [])


@pytest.mark.parametrize(
    "guard",
    [
        "cmd_off",
        "default",
        "object",
        "stdout",
        "background",
        "suspended",
        "bool_first",
        "bool_last",
    ],
)
def test_upstream_scope_guards(completed_pipeline, xonsh_session, guard):
    def unexpected(*args):
        pytest.fail("excluded pipeline evaluated an upstream policy")

    pipeline, restored = completed_pipeline(policies=(unexpected, None, None))
    if guard == "cmd_off":
        xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = False
    elif guard == "default":
        del xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"]
    elif guard in ("object", "stdout"):
        pipeline.captured = guard
    elif guard == "background":
        pipeline.spec.background = True
    elif guard == "suspended":
        pipeline.suspended = True
    else:
        pipeline.specs[0 if guard == "bool_first" else -1].in_boolop = True
    pipeline._raise_subproc_error()
    assert restored == []


@pytest.mark.parametrize("unknown", [None, "missing"])
@pytest.mark.parametrize("index", [0, 1])
def test_unknown_sibling_does_not_hide_failure(completed_pipeline, unknown, index):
    pipeline, restored = completed_pipeline()
    if unknown == "missing":
        pipeline.procs[index] = None
    else:

        class Unknown:
            returncode = None

            def poll(self):
                pytest.fail("upstream poll must not be called")

            wait = join = poll

        pipeline.procs[index] = Unknown()
    with pytest.raises(subprocess.CalledProcessError) as exc:
        pipeline._raise_subproc_error()
    assert exc.value.cmd == [f"stage-{1 - index}"]
    assert restored == [True]


@pytest.mark.parametrize("terminal_policy", [False, True, None])
def test_terminal_failure_precedence(completed_pipeline, terminal_policy):
    pipeline, restored = completed_pipeline(
        statuses=(7, 9, 11), policies=(True, True, terminal_policy)
    )
    if terminal_policy is False:
        pipeline._raise_subproc_error()
        assert restored == []
    else:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            pipeline._raise_subproc_error()
        assert (exc.value.returncode, exc.value.cmd) == (11, ["stage-2"])
        assert restored == [True]


@pytest.mark.parametrize("status", [0, None])
def test_no_completed_failure(completed_pipeline, status):
    pipeline, restored = completed_pipeline(
        statuses=(status, 0, 0), policies=(True, True, True)
    )
    pipeline._raise_subproc_error()
    assert restored == []


@skip_if_on_windows
@pytest.mark.parametrize(
    "status",
    [-signal.SIGPIPE if hasattr(signal, "SIGPIPE") else -13, -signal.SIGTERM, 141],
)
@pytest.mark.parametrize("policy", [None, True, False])
def test_upstream_signal_policy(completed_pipeline, status, policy):
    pipeline, restored = completed_pipeline(
        statuses=(status, 0, 0), policies=(policy, None, None)
    )
    raises = policy is not False and (status != -signal.SIGPIPE or policy is True)
    if raises:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            pipeline._raise_subproc_error()
        assert exc.value.returncode == status
    else:
        pipeline._raise_subproc_error()
    assert restored == ([True] if raises else [])


@skip_if_on_windows
@pytest.mark.parametrize("kind", ["sigpipe", "sigterm", "exit141"])
@pytest.mark.parametrize("force", [False, True])
def test_native_upstream_signal(xonsh_session, kind, force):
    from xonsh.procs.specs import SpecAttrDecoratorAlias, run_subproc

    xonsh_session.env["XONSH_SUBPROC_RAISE_ERROR"] = False
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    xonsh_session.aliases["@force"] = SpecAttrDecoratorAlias(
        {"raise_subproc_error": True}
    )
    if kind == "sigpipe":
        producer = (
            "import os,signal; signal.signal(signal.SIGPIPE, signal.SIG_DFL); "
            "exec('while True: os.write(1, b\"x\" * 65536)')"
        )
        consumer = "import sys; sys.stdin.buffer.read(1); print('consumed')"
        expected = -signal.SIGPIPE
    else:
        producer = (
            "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"
            if kind == "sigterm"
            else "import sys; sys.exit(141)"
        )
        consumer = "import sys; sys.stdin.read(); print('consumed')"
        expected = -signal.SIGTERM if kind == "sigterm" else 141
    command = [sys.executable, "-c", producer]
    cmds = [
        ["@force", *command] if force else command,
        "|",
        [sys.executable, "-c", consumer],
    ]
    if kind != "sigpipe" or force:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            run_subproc(cmds, "hiddenobject")
        assert (exc.value.returncode, exc.value.cmd) == (expected, cmds[0])
    else:
        run_subproc(cmds, "hiddenobject")
    pipeline = xonsh_session.lastcmd
    assert pipeline.pipestatus == [expected, 0]
    assert pipeline.returncode == 0
    assert bool(pipeline)
    pipeline.end()


@pytest.mark.parametrize("captured", ["object", "stdout"])
def test_native_upstream_capture_excluded(xonsh_session, captured):
    from xonsh.procs.specs import run_subproc

    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    xonsh_session.env["XONSH_SUBPROC_RAISE_ERROR"] = False
    result = run_subproc(
        [
            [sys.executable, "-c", "import sys; print('payload'); sys.exit(7)"],
            "|",
            [sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"],
        ],
        captured,
    )
    pipeline = xonsh_session.lastcmd
    pipeline.end()
    assert pipeline.pipestatus == [7, 0]
    assert pipeline.returncode == 0
    assert bool(pipeline)
    assert "payload" in (result if captured == "stdout" else pipeline.output)


def test_mixed_alias_native_upstream(xonsh_session):
    from xonsh.procs.specs import run_subproc

    def consume(args, stdin, stdout):
        stdout.write(stdin.read())

    xonsh_session.aliases["consume"] = consume
    xonsh_session.env["XONSH_SUBPROC_CMD_RAISE_ERROR"] = True
    command = [sys.executable, "-c", "import sys; print('payload'); sys.exit(7)"]
    with pytest.raises(subprocess.CalledProcessError) as exc:
        run_subproc([command, "|", ["consume"]], "hiddenobject")
    assert (exc.value.returncode, exc.value.cmd) == (7, command)
    assert xonsh_session.lastcmd.pipestatus == [7, 0]


def test_upstream_exception_preserves_terminal_bookkeeping(
    completed_pipeline, xonsh_session, monkeypatch
):
    from types import SimpleNamespace

    history = SimpleNamespace(last_cmd_rtn=None)
    with monkeypatch.context() as patch:
        patch.setattr(xonsh_session, "history", history)
        local = {}
        xonsh_session.env["__THREAD_LOCAL__"] = local
        pipeline, _ = completed_pipeline()
        pipeline._apply_to_history()
        pipeline._apply_to_thread_local()
        with pytest.raises(subprocess.CalledProcessError):
            pipeline._raise_subproc_error()
        assert history.last_cmd_rtn == local["returncode"] == pipeline.returncode == 0
        assert pipeline.pipecode == 1


def test_unknown_terminal_skips_upstream(completed_pipeline):
    def unexpected(*args):
        pytest.fail("unknown terminal must retain its existing path")

    pipeline, restored = completed_pipeline(
        statuses=(7, 9, None), policies=(unexpected, None, unexpected)
    )
    pipeline.proc.poll = lambda: None
    pipeline._raise_subproc_error()
    assert restored == []
