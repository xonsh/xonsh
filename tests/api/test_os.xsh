import os
import shutil
import tempfile

from xonsh.api.os import indir, rmtree

import pytest
from pathlib import Path
from xonsh.pytest.tools import ON_WINDOWS

def resolve_path(p):
    """Path can be a symlink (e.g. on macOS) so we need to resolve it first."""
    return str(Path(p).resolve())

def test_indir():
    if ON_WINDOWS:
        pytest.skip("On Windows")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = resolve_path(tmpdir)
        assert resolve_path($(pwd).strip()) != tmpdir
        with indir(tmpdir):
            assert resolve_path($(pwd).strip()) == tmpdir
        assert resolve_path($(pwd).strip()) != tmpdir
        try:
            with indir(tmpdir):
                raise Exception
        except Exception:
            assert resolve_path($(pwd).strip()) != tmpdir


def test_rmtree():
    if ON_WINDOWS:
        pytest.skip("On Windows")
    if shutil.which("git") is None:
        # The test seeds the temp dir with a .git/ to exercise rmtree on
        # a real working tree; without git on PATH (e.g. FreeBSD poudriere
        # build env) the seeding step aborts before rmtree is ever called.
        pytest.skip("git not on PATH — needed to seed the rmtree fixture")
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

