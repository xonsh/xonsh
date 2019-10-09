import os
import stat
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
    # This test has to include building a read-only file
    with tempfile.TemporaryDirectory() as tmpdir:
        with indir(tmpdir):
            # Get into directory
            mkdir rmtree_test
            pushd rmtree_test
            # Put something there
            with open('thing.txt', 'wt') as f:
                print("hello", file=f)
            os.chmod('thing.txt', stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            # Get out of it
            popd
            # Test that stuff got made
            assert os.path.exists('rmtree_test')
            assert os.path.exists('rmtree_test/thing.txt')
            assert not os.access('rmtree_test/thing.txt', os.W_OK)
            # Remove it
            rmtree('rmtree_test', force=True)
            # Test the previously made stuff no longer exists
            assert not os.path.exists('rmtree_test')
            assert not os.path.exists('rmtree_test/thing.txt')
