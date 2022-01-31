"""Testing xonsh json hooks"""
import json

import pytest

from xonsh.jsonutils import serialize_xonsh_json
from xonsh.tools import EnvPath


@pytest.mark.parametrize(
    "inp",
    [
        42,
        "yo",
        ["hello"],
        {"x": 65},
        EnvPath(["wakka", "jawaka"]),
        ["y", EnvPath(["wakka", "jawaka"])],
        {"z": EnvPath(["wakka", "jawaka"])},
    ],
)
def test_serialize_xonsh_json_roundtrip(inp):
    s = json.dumps(inp, default=serialize_xonsh_json)
    obs = json.loads(s)
    assert inp == obs
