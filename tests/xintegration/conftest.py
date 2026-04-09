"""Shared utilities for integration tests that run xonsh in a subprocess."""

import os
import shutil
import subprocess as sp

import pytest

PATH = (
    os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "bin")
    + os.pathsep
    + os.environ["PATH"]
)

skip_if_no_xonsh = pytest.mark.skipif(
    shutil.which("xonsh") is None, reason="xonsh not on PATH"
)
skip_if_no_make = pytest.mark.skipif(
    shutil.which("make") is None, reason="make command not on PATH"
)
skip_if_no_sleep = pytest.mark.skipif(
    shutil.which("sleep") is None, reason="sleep command not on PATH"
)

base_env = {
    "PATH": PATH,
    "XONSH_DEBUG": "0",
    "XONSH_SHOW_TRACEBACK": "1",
    "XONSH_SUBPROC_CMD_RAISE_ERROR": "0",
    "XONSH_SUBPROC_RAISE_ERROR": "0",
    "FOREIGN_ALIASES_SUPPRESS_SKIP_MESSAGE": "1",
    "PROMPT": "",
    "TERM": "linux",  # disable ansi escape codes
}


def run_xonsh(
    cmd,
    stdin=sp.PIPE,
    stdin_cmd=None,
    stdout=sp.PIPE,
    stderr=sp.STDOUT,
    single_command=False,
    interactive=False,
    path=None,
    args=None,
    timeout=20,
    env=None,
    blocking=True,
    xonsh_cmd="python -m xonsh",
):
    # Env
    popen_env = dict(os.environ)
    popen_env |= base_env
    if path:
        popen_env["PATH"] = path
    if env:
        popen_env |= env

    # Args
    xonsh_cmd = xonsh_cmd.split()
    xonsh_cmd[0] = shutil.which(xonsh_cmd[0], path=PATH)
    popen_args = xonsh_cmd

    if not args:
        popen_args += ["--no-rc"]
    else:
        popen_args += args

    if interactive:
        popen_args.append("-i")
        if cmd and isinstance(cmd, str) and not cmd.endswith("\n"):
            # In interactive mode we need to emulate "Press Enter".
            cmd += "\n"

    if single_command:
        popen_args += ["-c", cmd]
        input = None
    else:
        input = cmd

    proc = sp.Popen(
        popen_args,
        env=popen_env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        universal_newlines=True,
    )

    if stdin_cmd:
        proc.stdin.write(stdin_cmd)
        proc.stdin.flush()

    if not blocking:
        return proc

    try:
        out, err = proc.communicate(input=input, timeout=timeout)
    except sp.TimeoutExpired:
        proc.kill()
        raise
    return out, err, proc.returncode


def check_run_xonsh(cmd, fmt, exp, exp_rtn=0):
    """The ``fmt`` parameter is a function
    that formats the output of cmd, can be None.
    """
    out, err, rtn = run_xonsh(cmd, stderr=sp.PIPE)
    if callable(fmt):
        out = fmt(out)
    if callable(exp):
        exp = exp()
    assert out == exp, err
    assert rtn == exp_rtn, err
