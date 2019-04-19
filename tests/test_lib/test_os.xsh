import os
import tempfile

from xonsh.lib.os import indir, rmtree

import pytest

from tools import ON_WINDOWS


def test_indir():
    if ON_WINDOWS:
        pytest.skip("On Windows")
    with tempfile.TemporaryDirectory() as tmpdir:
        assert ![pwd].output.strip() != tmpdir
        with indir(tmpdir):
            assert ![pwd].output.strip() == tmpdir
        assert ![pwd].output.strip() != tmpdir
        try:
            with indir(tmpdir):
                raise Exception
        except Exception:
            assert ![pwd].output.strip() != tmpdir


def test_rmtree():
    with tempfile.TemporaryDirectory() as tmpdir:
        with indir(tmpdir):
            mkdir rmtree_test
            pushd rmtree_test
            git init
            git config user.email "test@example.com"
            git config user.name "Code Monkey"
            touch thing.txt
            git add thing.txt
            git commit -a --no-gpg-sign -m "add thing"
            popd
            assert os.path.exists('rmtree_test')
            assert os.path.exists('rmtree_test/thing.txt')
            rmtree('rmtree_test', force=True)
            assert not os.path.exists('rmtree_test')
            assert not os.path.exists('rmtree_test/thing.txt')

