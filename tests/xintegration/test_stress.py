"""Stress tests for callable aliases, pipes, and fd leaking.

These tests run xonsh in a subprocess with heavy workloads
and long timeouts. Separated from test_integrations.py to allow
running quick integration tests without waiting for stress tests.
"""

import re

import pytest

from tests.xintegration.conftest import run_xonsh
from xonsh.pytest.tools import skip_if_on_windows


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_alias_stability():
    """Testing alias stability after amalgamation regress that described in #5435."""
    stdin_cmd = (
        "aliases['tst'] = lambda: [print('sleep'), __import__('time').sleep(1)]\n"
        "tst\ntst\ntst\n"
    )
    out, err, ret = run_xonsh(
        cmd=None,
        stdin_cmd=stdin_cmd,
        interactive=True,
        single_command=False,
        timeout=10,
    )
    assert re.match(".*sleep.*sleep.*sleep.*", out, re.MULTILINE | re.DOTALL)


@skip_if_on_windows
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_alias_stability_exception():
    """Testing alias stability (exception) after amalgamation regress that described in #5435."""
    stdin_cmd = (
        "aliases['tst1'] = lambda: [print('sleep'), __import__('time').sleep(1)]\n"
        "aliases['tst2'] = lambda: [1/0]\n"
        "tst1\ntst2\ntst1\ntst2\n"
    )
    out, err, ret = run_xonsh(
        cmd=None,
        stdin_cmd=stdin_cmd,
        interactive=True,
        single_command=False,
        timeout=10,
    )
    assert re.match(
        ".*sleep.*ZeroDivisionError.*sleep.*ZeroDivisionError.*",
        out,
        re.MULTILINE | re.DOTALL,
    )
    assert "Bad file descriptor" not in out


test_code_no_bad_fd = [
    """
$XONSH_SHOW_TRACEBACK = True
@aliases.register
def _e(a,i,o,e):
    echo -n O
    echo -n E 1>2
    # execx("echo -n O")      # Excluded until fix https://github.com/xonsh/xonsh/issues/5631
    # execx("echo -n E 1>2")  # Excluded until fix https://github.com/xonsh/xonsh/issues/5631
    print("o")
    print("O", file=o)
    print("E", file=e)

import tempfile
for i in range(0, 12):
    echo -n e
    print($(e), !(e), $[e], ![e])
    print($(e > @(tempfile.NamedTemporaryFile(delete=False).name)))
    print(!(e > @(tempfile.NamedTemporaryFile(delete=False).name)))
    print($[e > @(tempfile.NamedTemporaryFile(delete=False).name)])
    print(![e > @(tempfile.NamedTemporaryFile(delete=False).name)])
"""
]


@skip_if_on_windows
@pytest.mark.parametrize("test_code", test_code_no_bad_fd)
def test_callable_alias_no_bad_file_descriptor(test_code):
    """Test no exceptions during any kind of capturing of callable alias. See also #5631."""

    out, err, ret = run_xonsh(
        test_code, interactive=False, single_command=True, timeout=60
    )
    assert ret == 0
    assert "Error" not in out
    assert "Exception" not in out


# Number of ``a | b`` pipe calls made by ``test_code_fd_leaking``.  A few
# warm-up calls first, because xonsh opens some descriptors lazily and the
# baseline has to be taken once the shell reached a steady state.
FD_LEAKING_WARMUP_CALLS = 11
FD_LEAKING_CALLS = 189

_code_fd_leaking = """
$XONSH_SHOW_TRACEBACK = True
import os
import sys

def _open_fds():
    # Number of open file descriptors, or None on platforms that expose no
    # descriptor directory (Windows), where the check is skipped.
    for _p in ("/proc/self/fd", "/dev/fd"):
        if os.path.isdir(_p):
            return len(os.listdir(_p))
    return None

@aliases.register
def _a(args, stdin, stdout, stderr):
    name = 'a'

    print(f"{name}: print out alias.stdout", file=stdout)
    print(f"{name}: print err alias.stderr", file=stderr)

    print(f"{name}: print out sys.stdout", file=sys.stdout)
    print(f"{name}: print err sys.stderr", file=sys.stderr)

    echo @(f"{name}: echo stdout")
    echo @(f"{name}: echo stderr") o>e

    ![echo @(f"{name}: ![] echo stdout")]
    $[echo @(f"{name}: $[] echo stdout")]

    $(echo @(f"{name}: $() echo stdout LEAKING TEST"))
    $(echo @(f"{name}: $() echo stderr") o>e)

    !(echo @(f"{name}: !() echo stdout LEAKING TEST"))
    !(echo @(f"{name}: !() echo stderr LEAKING TEST") o>e)

    execx(f'echo "{name}: execx echo stdout"')
    execx(f'echo "{name}: execx echo stderr" o>e')

    echo 1 && echo 2


@aliases.register
def _b(args, stdin, stdout, stderr):
    name = 'b'

    print(f"{name}: print out alias.stdout", file=stdout)
    print(f"{name}: print err alias.stderr", file=stderr)

    print(f"{name}: print out sys.stdout", file=sys.stdout)
    print(f"{name}: print err sys.stderr", file=sys.stderr)

    echo @(f"{name}: echo stdout")
    echo @(f"{name}: echo stderr") o>e

    ![echo @(f"{name}: ![] echo stdout")]
    $[echo @(f"{name}: $[] echo stdout")]

    $(echo @(f"{name}: $() echo stdout LEAKING TEST"))
    $(echo @(f"{name}: $() echo stderr") o>e)

    !(echo @(f"{name}: !() echo stdout LEAKING TEST"))
    !(echo @(f"{name}: !() echo stderr LEAKING TEST") o>e)

    execx(f'echo "{name}: execx echo stdout"')
    execx(f'echo "{name}: execx echo stderr" o>e')

    echo 3 && echo 4

for i in range(WARMUP_CALLS):
    $(a | b)

_fds_before = _open_fds()

for i in range(CALLS):
    $(a | b)

_fds_after = _open_fds()

if _fds_before is not None and _fds_after > _fds_before:
    # The marker is deliberately free of digits: the test asserts that no
    # digit leaks from alias `a` into the output.
    print("FDLEAK", file=sys.stderr)
"""

test_code_fd_leaking = [
    _code_fd_leaking.replace("WARMUP_CALLS", str(FD_LEAKING_WARMUP_CALLS)).replace(
        "CALLS", str(FD_LEAKING_CALLS)
    )
]


@pytest.mark.parametrize("test_code", test_code_fd_leaking)
@pytest.mark.timeout(600)
def test_callable_alias_fd_leaking(test_code):
    """Testing callable alias on leaks and errors in pipe.
    1. No fd leaking: the number of open descriptors is stable across
       hundreds of pipe calls, and the output is never interrupted.
    2. No I/O errors or "Bad file descriptor" errors.
    3. No stdout leaking from alias `a`.
    See also #6159.
    """

    out, err, ret = run_xonsh(
        test_code, interactive=False, single_command=True, timeout=600
    )
    assert ret == 0
    assert "Error" not in out  # No I/O errors or "Bad file descriptor" errors.
    assert "Exception" not in out  # No I/O errors or "Bad file descriptor" errors.
    assert "LEAKING" not in out  # No captured stdout/stderr leaking.
    assert "FDLEAK" not in out  # No fd leaking.
    # No output interrupting.
    assert out.count("3\\n4\\n") == FD_LEAKING_WARMUP_CALLS + FD_LEAKING_CALLS
    assert "1" not in out  # No stdout leaking from alias `a`.
    assert "2" not in out  # No stdout leaking from alias `a`.


@skip_if_on_windows
@pytest.mark.timeout(120)
def test_pipe_into_callable_alias_no_bad_fd_stress():
    """Stress test for `<fast subprocess> | <callable alias reading stdin>`.

    Regression test: ``CommandPipeline._prev_procs_done`` used to call
    ``ch.close()`` on the connecting pipe between a fast-finishing
    upstream subprocess and a callable alias still iterating over its
    stdin TextIOWrapper.  Closing the read end mid-iteration surfaced as
    ``OSError: [Errno 9] Bad file descriptor`` printed to stderr.

    Run a heavy loop with several common patterns so that the race
    triggers reliably and any future regression on CI is unmissable.
    """
    test_code = r"""
$XONSH_SHOW_TRACEBACK = True

@aliases.register
def _addsuffix(args, stdin, stdout, stderr):
    suffix = args[0] if args else ''
    for line in stdin or []:
        stdout.write(line.upper() + suffix)

@aliases.register
def _takeall(args, stdin, stdout, stderr):
    for line in stdin or []:
        stdout.write(line)

# A: subprocess -> callable alias (the original failing case).
for i in range(50):
    echo -n 'hello ' | addsuffix snail

# B: subprocess -> callable alias, captured forms.
for i in range(50):
    print($(echo -n 'hi' | addsuffix !), end='')
    print(!(echo -n 'hi' | addsuffix !).out, end='')

# C: multi-line input.
for i in range(50):
    printf 'a\nb\nc' | takeall
"""
    out, err, ret = run_xonsh(
        test_code, interactive=False, single_command=True, timeout=120
    )
    assert ret == 0, f"non-zero exit; out={out!r} err={err!r}"
    assert "Bad file descriptor" not in out
    assert "Bad file descriptor" not in (err or "")
    assert "Exception in thread" not in out
    assert "Exception in thread" not in (err or "")
