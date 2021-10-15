"""Tests the xonsh.procs.specs"""
import itertools
import sys
from subprocess import Popen

import pytest

from xonsh.procs.specs import cmds_to_specs, run_subproc
from xonsh.built_ins import XSH
from xonsh.procs.posix import PopenThread
from xonsh.procs.proxies import ProcProxy, ProcProxyThread, STDOUT_DISPATCHER

from tests.tools import skip_if_on_windows


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
def test_cmds_to_specs_capture_stdout_not_stderr(thread_subprocs):
    env = XSH.env
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
@pytest.mark.flaky(reruns=5, reruns_delay=2)
def test_capture_always(
    capfd, thread_subprocs, capture_always, alias_type, pipe, monkeypatch
):
    if not thread_subprocs and alias_type in ["func", "exec"]:
        if pipe:
            return pytest.skip("https://github.com/xonsh/xonsh/issues/4443")
        else:
            return pytest.skip("https://github.com/xonsh/xonsh/issues/4444")

    env = XSH.env
    exp = "HELLO\nBYE\n"
    cmds = [["echo", "-n", exp]]
    if pipe:
        exp = exp.splitlines()[1] + "\n"  # second line
        cmds += ["|", ["grep", "--color=never", exp.strip()]]

    if alias_type:
        first_cmd = cmds[0]
        # Enable capfd for function aliases:
        monkeypatch.setattr(STDOUT_DISPATCHER, "default", sys.stdout)
        if alias_type == "func":
            XSH.aliases["tst"] = (
                lambda: run_subproc([first_cmd], "hiddenobject") and None
            )  # Don't return a value
        elif alias_type == "exec":
            first_cmd = " ".join(repr(arg) for arg in first_cmd)
            XSH.aliases["tst"] = f"![{first_cmd}]"
        else:
            # alias_type == "simple"
            XSH.aliases["tst"] = first_cmd

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
@pytest.mark.parametrize(
    "captured, exp_is_none",
    [
        ("object", False),
        ("stdout", True),
        ("hiddenobject", True),
        (False, True),
    ],
)
def test_run_subproc_background(captured, exp_is_none):

    cmds = (["echo", "hello"], "&")
    return_val = run_subproc(cmds, captured)
    assert (return_val is None) == exp_is_none


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
