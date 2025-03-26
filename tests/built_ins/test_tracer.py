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
    env = {"XONSH_SHOW_TRACEBACK": "True"}
    if sys.platform == "win32":
        # required for an empty environment on Windows. see python/cpython#120836
        for ev in W_ENV.split():
            env[ev] = os.environ[ev]
    expected = dedent(
        """\
        Some output!
        tests/built_ins/tracer/example.xsh:3:variable = ""
        tests/built_ins/tracer/example.xsh:4:for part in parts:
        tests/built_ins/tracer/example.xsh:5:    variable += part
        tests/built_ins/tracer/example.xsh:4:for part in parts:
        tests/built_ins/tracer/example.xsh:5:    variable += part
        tests/built_ins/tracer/example.xsh:4:for part in parts:
        tests/built_ins/tracer/example.xsh:5:    variable += part
        tests/built_ins/tracer/example.xsh:4:for part in parts:
        tests/built_ins/tracer/example.xsh:6:echo Some @(variable)
        """
    ).replace("/", os.sep)
    proc = subprocess.run(cmd, capture_output=True, encoding="utf8", env=env)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert proc.stdout == expected
