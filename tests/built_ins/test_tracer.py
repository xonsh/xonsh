import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from xonsh.procs.specs import cmds_to_specs
from xonsh.tracer import tracermain

# Minimum set of environment variables on Windows
W_ENV = "SYSTEMDRIVE SYSTEMROOT ALLUSERSPROFILE HOMEDRIVE HOMEPATH APPDATA LOCALAPPDATA"


def test_tracer_help(capsys, xsh_with_aliases):
    """verify can invoke it, and usage knows about all the options"""
    spec = cmds_to_specs([("trace", "-h")], captured="stdout")[0]
    with pytest.raises(SystemExit):
        tracermain(["-h"], spec=spec)
    capout = capsys.readouterr().out
    pat = re.compile(r"^usage:\s*trace[^\n]*{([\w,-]+)}", re.MULTILINE)
    m = pat.match(capout)
    assert m[1]
    verbs = {v.strip().lower() for v in m[1].split(",")}
    assert verbs == {"rm", "start", "add", "on", "off", "del", "color", "stop", "ls"}


def test_trace_in_script():
    CURRENT_DIR = Path(__file__).parent
    cmd = [sys.executable, "-m", "xonsh", str(CURRENT_DIR / "tracer" / "example.xsh")]
    env = os.environ  # We need to use real env or xonsh.platform.PATH_DEFAULT to have NixOS coreutils support.
    env["XONSH_SHOW_TRACEBACK"] = "1"
    if sys.platform == "win32":
        # required for an empty environment on Windows. see python/cpython#120836
        for ev in W_ENV.split():
            env[ev] = os.environ[ev]
    expected = dedent(
        """\
        example.xsh:3:variable = ""
        example.xsh:4:for part in parts:
        example.xsh:5:    variable += part
        example.xsh:4:for part in parts:
        example.xsh:5:    variable += part
        example.xsh:4:for part in parts:
        example.xsh:5:    variable += part
        example.xsh:4:for part in parts:
        example.xsh:6:echo Some @(variable)"""
    ).replace("/", os.sep)
    output = "Some output!\n"

    proc = subprocess.run(cmd, capture_output=True, encoding="utf8", env=env)
    # Remove path to example script from stdout.
    stdout = re.sub(r".*example\.xsh:", "example.xsh:", proc.stdout)
    assert proc.returncode == 0
    assert proc.stderr == ""
    # Trace lines must precede subprocess output: the tracer flushes stdout
    # after each line, so trace output cannot be reordered with respect to
    # subprocesses spawned on the same line. See xonsh/xonsh#3291.
    assert stdout == expected + "\n" + output


def test_trace_in_script_with_logging_handler():
    """Regression for xonsh/xonsh#4924: a `logging.Handler` weakref callback
    must not blow up at interpreter shutdown while `trace on` is active. The
    assertion is `proc.stderr == ""` — any "Exception ignored in..." traceback
    from `_removeHandlerRef` would land there.

    The original report (Python 3.10 + Anaconda on Linux) reliably triggered
    the shutdown race; CPython 3.13 reorders module finalization and may not.
    This test stays as an end-to-end sanity check; the unit test below
    deterministically pins the invariant on every platform.
    """
    CURRENT_DIR = Path(__file__).parent
    cmd = [
        sys.executable,
        "-m",
        "xonsh",
        str(CURRENT_DIR / "tracer" / "example_logging.xsh"),
    ]
    env = os.environ.copy()
    env["XONSH_SHOW_TRACEBACK"] = "1"
    if sys.platform == "win32":
        for ev in W_ENV.split():
            env[ev] = os.environ[ev]
    proc = subprocess.run(cmd, capture_output=True, encoding="utf8", env=env)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert "OK" in proc.stdout


def test_tracer_skips_untraced_frames():
    """Regression for xonsh/xonsh#3063: when the global trace function fires
    on a 'call' event for a frame whose file is not in ``self.files``,
    ``trace()`` must return ``None`` so Python skips installing the per-frame
    tracer. Without this, line events fire for every line of every imported
    module while ``trace on`` is active, slowing scripts by ~100× on the
    original report.
    """
    import inspect

    import xonsh.tracer as tm

    t = tm.TracerType()
    t.files = set()
    # 'call' is the event that wires up per-frame tracing; 'line' fires only
    # for frames already opted in. Both must short-circuit to None when the
    # frame's file isn't traced.
    assert t.trace(inspect.currentframe(), "call", None) is None
    assert t.trace(inspect.currentframe(), "line", None) is None


def test_tracer_caches_filename_per_code_object():
    """``trace()`` resolves the frame's filename via ``find_file``, which
    calls ``inspect.getabsfile`` + ``normabspath`` — non-trivial cost on the
    hot path. The result is cached per code object (see #3063); a single
    call should populate the cache, and the cache must survive across
    repeated calls for the same code object.
    """
    import inspect

    import xonsh.tracer as tm

    t = tm.TracerType()
    t._fname_cache.clear()
    frame = inspect.currentframe()
    t.files = set()
    t.trace(frame, "call", None)
    assert frame.f_code in t._fname_cache


def test_tracer_survives_module_finalization():
    """Regression for xonsh/xonsh#4924: when CPython tears down modules at
    interpreter exit, `xonsh.tracer`'s globals can be wiped while `trace` is
    still installed via `sys.settrace`. Weakref callbacks (e.g.
    `logging._removeHandlerRef`) firing in that window re-enter `trace`,
    which must still resolve its cross-module imports. The fix in #5806 (and
    the extension above) keeps those names alive via `__kwdefaults__` rather
    than module globals. This test wipes the globals by hand and confirms
    `trace()` runs without raising.
    """
    import inspect

    import xonsh.tracer as tm

    fragile = ["find_file", "print_color", "linecache", "sys"]
    saved = {name: tm.__dict__.get(name) for name in fragile}
    for name in fragile:
        tm.__dict__[name] = None
    try:
        t = tm.TracerType()
        # files is empty → trace() invokes find_file() then exits before
        # touching print_color / linecache / sys. find_file is the lookup
        # that historically blew up first (#4924 traceback line 87).
        t.trace(inspect.currentframe(), "line", None)
    finally:
        tm.__dict__.update(saved)
