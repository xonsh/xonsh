import re

import pytest

from xonsh.procs.specs import cmds_to_specs
from xonsh.tracer import tracermain


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
