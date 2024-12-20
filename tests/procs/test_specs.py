"""Tests the xonsh.procs.specs"""

import itertools
import signal
import sys
from subprocess import CalledProcessError, Popen

import pytest

from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import STDOUT_DISPATCHER, ProcProxy, ProcProxyThread
from xonsh.procs.specs import (
    DecoratorAlias,
    SpecAttrDecoratorAlias,
    SubprocSpec,
    _run_command_pipeline,
    cmds_to_specs,
    run_subproc,
)
from xonsh.pytest.tools import ON_WINDOWS, VER_MAJOR_MINOR, skip_if_on_windows
from xonsh.tools import XonshError

# TODO: track down which pipeline + spec test is hanging CI
# Skip entire test file for Linux on Python 3.12
pytestmark = pytest.mark.skipif(
    not ON_WINDOWS and VER_MAJOR_MINOR == (3, 12),
    reason="Backgrounded test is hanging on CI on 3.12 only",
    allow_module_level=True,
)


def cmd_sig(sig):
    return [
        "python",
        "-c",
        f"import os, signal; os.kill(os.getpid(), signal.{sig})",
    ]


@skip_if_on_windows
def test_cmds_to_specs_thread_subproc(xession):
    env = xession.env
    cmds = [["pwd"]]

    # XONSH_CAPTURE_ALWAYS=False should disable interactive threaded subprocs
    env["XONSH_CAPTURE_ALWAYS"] = False
    env["THREAD_SUBPROCS"] = True
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is Popen

    # Now for the other situations
    env["XONSH_CAPTURE_ALWAYS"] = True

    # First check that threadable subprocs become threadable
    env["THREAD_SUBPROCS"] = True
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is PopenThread
    # turn off threading and check we use Popen
    env["THREAD_SUBPROCS"] = False
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is Popen

    # now check the threadbility of callable aliases
    cmds = [[lambda: "Keras Selyrian"]]
    # check that threadable alias become threadable
    env["THREAD_SUBPROCS"] = True
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is ProcProxyThread
    # turn off threading and check we use ProcProxy
    env["THREAD_SUBPROCS"] = False
    specs = cmds_to_specs(cmds, captured="hiddenobject")
    assert specs[0].cls is ProcProxy


@pytest.mark.parametrize("thread_subprocs", [True, False])
def test_cmds_to_specs_capture_stdout_not_stderr(thread_subprocs, xonsh_session):
    env = xonsh_session.env
    cmds = (["ls", "/root"],)

    env["THREAD_SUBPROCS"] = thread_subprocs

    specs = cmds_to_specs(cmds, captured="stdout")
    assert specs[0].stdout is not None
    assert specs[0].stderr is None


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
            xonsh_session.aliases["tst"] = (
                lambda: run_subproc([first_cmd], "hiddenobject") and None
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
    if thread_subprocs:
        assert exp not in capfd.readouterr().out
        assert hidden.out == exp
    else:
        # for some reason THREAD_SUBPROCS=False fails to capture in `!()` but still succeeds in `$()`
        assert exp in capfd.readouterr().out
        assert not hidden.out

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
    xonsh_session.env["RAISE_SUBPROC_ERROR"] = False
    cmd = [cmd_sig("SIGINT")]
    specs = cmds_to_specs(cmd, captured="stdout")
    (p := _run_command_pipeline(specs, cmd)).end()
    assert p.proc.returncode == -signal.SIGINT


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_proc_raise_subproc_error(xonsh_session):
    xonsh_session.env["RAISE_SUBPROC_ERROR"] = False

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

    xonsh_session.env["RAISE_SUBPROC_ERROR"] = True
    specs = cmds_to_specs(cmd := [["ls", "nofile"]], captured="stdout")
    exception = None
    try:
        (p := _run_command_pipeline(specs, cmd)).end()
    except Exception as e:
        assert p.proc.returncode > 0
        exception = e
    assert isinstance(exception, CalledProcessError)


@skip_if_on_windows
@pytest.mark.parametrize(
    "suspended_pipeline",
    [
        [cmd_sig("SIGTTIN")],
        [["echo", "1"], "|", cmd_sig("SIGTTIN")],
        [["echo", "1"], "|", cmd_sig("SIGTTIN"), "|", ["head"]],
    ],
)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_specs_with_suspended_captured_process_pipeline(
    xonsh_session, suspended_pipeline
):
    xonsh_session.env["XONSH_INTERACTIVE"] = True
    specs = cmds_to_specs(suspended_pipeline, captured="object")
    p = _run_command_pipeline(specs, suspended_pipeline)
    p.proc.send_signal(signal.SIGCONT)
    p.end()
    assert p.suspended


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
def test_run_subproc_background(captured, exp_is_none):
    cmds = (["echo", "hello"], "&")
    return_val = run_subproc(cmds, captured)
    assert (return_val is None) == exp_is_none


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


def test_redirect_to_substitution(xession):
    s = SubprocSpec.build(
        # `echo hello > @('file')`
        ["echo", "hello", (">", ["file"])]
    )
    assert s.stdout.name == "file"


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

    @xession.aliases.register("xsudo")
    @xession.aliases.return_command
    def _midground(args, decorators=None):
        return [
            "sudo",
            *xession.aliases.eval_alias(args, decorators=decorators),
        ]

    xession.aliases["cmd"] = "xthread echo 1"

    cmds = [
        ["xsudo", "cmd"],
    ]
    spec = cmds_to_specs(cmds, captured="object")[-1]
    assert spec.cmd == ["sudo", "echo", "1"]
    assert spec.alias_name == "xsudo"
    assert spec.threadable is True


def test_auto_cd(xession, tmpdir):
    xession.aliases["cd"] = lambda: "some_cd_alias"
    dir = str(tmpdir)
    with xession.env.swap(AUTO_CD=True):
        spec = cmds_to_specs([[dir]], captured="object")[-1]
    assert spec.alias.__name__ == "cd"
    assert spec.cmd[0] == dir
