import os
import tempfile
from xonsh.lib.os import indir


def test_indir():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert ![pwd].output.strip() != tmpdir
        with indir(tmpdir):
            assert ![pwd].output.strip() == tmpdir
        assert ![pwd].output.strip() != tmpdir
