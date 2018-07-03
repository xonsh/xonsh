import os
from xonsh.lib.os import indir

def test_indir():
    path = os.path.dirname(__file__)
    assert ![pwd].output.strip() != path
    with indir(path):
        assert ![pwd].output.strip() == path
    assert ![pwd].output.strip() != path
