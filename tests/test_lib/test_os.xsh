import os
import tempfile
from xonsh.lib.os import indir, rmtree


def test_indir():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert ![pwd].output.strip() != tmpdir
        with indir(tmpdir):
            assert ![pwd].output.strip() == tmpdir
        assert ![pwd].output.strip() != tmpdir

def test_rmtree():
    with tempfile.TemporaryDirectory as tmpdir:
        with indir(tmpdir):
            mkdir rmtree_test
            pushd rmtree_test
            git init
            touch thing.txt
            git add thing
            git commit -am "add thing"
            popd
            assert os.path.exists('rmtree_test')
            assert os.path.exists('rmtree_test/thing.txt')
            rmtree('rmtree_test')
            assert not os.path.exists('rmtree_test')
            assert not os.path.exists('rmtree_test/thing.txt')

