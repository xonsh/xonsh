"""Invocation ownership regressions for subprocess helpers."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from subprocess import CalledProcessError

import pytest

from xonsh.built_ins import (
    subproc_captured_hiddenobject,
    subproc_captured_inject,
    subproc_captured_object,
    subproc_captured_stdout,
    subproc_check_boolop,
    subproc_uncaptured,
)
from xonsh.procs import pipelines, specs
from xonsh.tools import unthreadable


@pytest.fixture
def capture_interleaving(monkeypatch, xonsh_session):
    """Pause a real child's owner before read while another helper finishes."""
    xonsh_session.env.update(
        # Keep helper calls concurrent without the unrelated nested I/O reader.
        THREAD_SUBPROCS=False,
        XONSH_SUBPROC_RAISE_ERROR=True,
        XONSH_SUBPROC_CMD_RAISE_ERROR=False,
    )
    first_done = threading.Event()
    owner_reading = threading.Event()
    release_owner = threading.Event()
    original_run = specs._run_specs
    original_read = pipelines._read_all
    owners = {}
    children = []

    def run(spec_list, cmds):
        name = threading.current_thread().name
        owners[name] = cmds[0][-1]
        if owners[name] == "second":
            assert first_done.wait(10), "first child did not finish"
        result = original_run(spec_list, cmds)
        if owners[name] == "first":
            first_done.set()
            assert owner_reading.wait(10), "second child did not reach read"
        return result

    def read(stream):
        if owners.get(threading.current_thread().name) == "second":
            owner_reading.set()
            assert release_owner.wait(10), "owner was not released"
        return original_read(stream)

    original_pipeline = specs._run_command_pipeline

    def pipeline(*args):
        cp = original_pipeline(*args)
        children.append(cp)
        return cp

    monkeypatch.setattr(specs, "_run_specs", run)
    monkeypatch.setattr(specs, "_run_command_pipeline", pipeline)
    monkeypatch.setattr(pipelines, "_read_all", read)

    def invoke(
        helper=subproc_captured_stdout, statuses=(0, 0), submit=None, wrap=False
    ):
        def child(label, status):
            try:
                selected = helper if label == "first" else subproc_captured_stdout
                result = selected(
                    [
                        sys.executable,
                        "-c",
                        "import sys; print(sys.argv[2]); sys.exit(int(sys.argv[1]))",
                        str(status),
                        label,
                    ],
                    in_boolop=wrap,
                )
                return subproc_check_boolop(result) if wrap else result
            except CalledProcessError as error:
                return error
            finally:
                if label == "first":
                    release_owner.set()

        if submit is None:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(child, label, status)
                    for label, status in zip(("first", "second"), statuses, strict=True)
                ]
                return [f.result(timeout=15) for f in futures]
        return submit(child)

    try:
        yield invoke
    finally:
        release_owner.set()
        first_done.set()
        owner_reading.set()
        for cp in children:
            if cp.proc is not None:
                cp.proc.wait(timeout=10)
            cp.end()


@pytest.mark.parametrize(
    "helper, first_output",
    [
        (subproc_captured_stdout, "first"),
        (subproc_captured_inject, ["first"]),
        (subproc_uncaptured, None),
    ],
)
@pytest.mark.parametrize("statuses", [(0, 0), (0, 7), (9, 0)])
@pytest.mark.parametrize("wrap", [False, True])
def test_capture_owns_pipeline(
    capture_interleaving, helper, first_output, statuses, wrap, xonsh_session
):
    results = capture_interleaving(helper, statuses, wrap=wrap)
    assert xonsh_session.lastcmd.spec.args[-1] == "second"
    assert xonsh_session.interface.lastcmd is xonsh_session.lastcmd
    assert xonsh_session.last is xonsh_session.lastcmd
    for index, (result, status) in enumerate(zip(results, statuses, strict=True)):
        label = ("first", "second")[index]
        if status:
            assert isinstance(result, CalledProcessError)
            assert result.returncode == status
            assert result.cmd == [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[2]); sys.exit(int(sys.argv[1]))",
                str(status),
                label,
            ]
            assert result.output == (
                label if index or helper is not subproc_uncaptured else ""
            )
        else:
            assert result == ("second" if index else first_output)


@pytest.mark.parametrize("threadable", [False, True])
def test_nested_capture_restores_invocation(xonsh_session, threadable):
    """An alias can capture children while its own pipeline is ending."""

    def nested(args):
        assert (
            subproc_captured_stdout([sys.executable, "-c", "print('inner')"]) == "inner"
        )
        assert subproc_captured_inject(
            [sys.executable, "-c", "print('two words')"]
        ) == ["two", "words"]
        return "outer\n", None, 6

    xonsh_session.aliases["nested_capture"] = (
        nested if threadable else unthreadable(nested)
    )
    xonsh_session.env.update(
        XONSH_SUBPROC_RAISE_ERROR=True,
        XONSH_SUBPROC_CMD_RAISE_ERROR=False,
    )
    with pytest.raises(CalledProcessError) as raised:
        subproc_captured_stdout(["nested_capture"])
    assert raised.value.returncode == 6
    assert raised.value.cmd == ["nested_capture"]
    assert raised.value.output == "outer"


@pytest.mark.parametrize(
    "captured", [subproc_captured_object, subproc_captured_hiddenobject]
)
def test_object_carries_own_status(xonsh_session, captured):
    # The CI runner enables per-command raising; this tests helper-level policy.
    xonsh_session.env.update(
        XONSH_SUBPROC_RAISE_ERROR=True,
        XONSH_SUBPROC_CMD_RAISE_ERROR=False,
    )
    command = [sys.executable, "-c", "print('object'); raise SystemExit(8)"]
    pipeline = captured(command)
    try:
        assert pipeline.returncode == 8
        assert pipeline.output == (
            "object" if captured is subproc_captured_object else ""
        )
        if captured is subproc_captured_object:
            assert subproc_check_boolop(pipeline) is pipeline
        else:
            with pytest.raises(CalledProcessError) as raised:
                subproc_check_boolop(pipeline)
            assert raised.value.cmd == command
            assert raised.value.returncode == 8
            assert raised.value.output == ""
    finally:
        pipeline.end()


@pytest.mark.parametrize(
    "output_format, expected",
    [
        ("stream_lines", "one\ntwo\n"),
        ("list_lines", ["one", "two"]),
    ],
)
def test_capture_format_contract(xonsh_session, output_format, expected):
    xonsh_session.env["XONSH_SUBPROC_OUTPUT_FORMAT"] = output_format
    assert (
        subproc_captured_stdout([sys.executable, "-c", "print('one'); print('two')"])
        == expected
    )


def test_disabled_raise_does_not_touch_other_capture(
    capture_interleaving, xonsh_session
):
    xonsh_session.env["XONSH_SUBPROC_RAISE_ERROR"] = False
    assert capture_interleaving(statuses=(7, 0), wrap=True) == ["first", "second"]
