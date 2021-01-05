import os
from pathlib import Path
import shutil
import subprocess as sp
import tempfile
from unittest.mock import Mock

import pytest

from xonsh.environ import Env
from xonsh.prompt import vc
from tools import DummyEnv


# Xonsh interaction with version control systems.
VC_BRANCH = {"git": {"master", "main"}, "hg": {"default"}}


@pytest.fixture(params=VC_BRANCH.keys())
def test_repo(request, tmpdir_factory):
    """Return a dict with vc and a temporary dir
    that is a repository for testing.
    """
    vc = request.param
    temp_dir = Path(tmpdir_factory.mktemp("dir"))
    os.chdir(temp_dir)
    try:
        sp.call([vc, "init"])
    except FileNotFoundError:
        pytest.skip("cannot find {} executable".format(vc))
    if vc == "git":
        git_config = temp_dir / ".git/config"
        git_config.write_text(
            """
[user]
name = me
email = my@email.address
"""
        )

        # git needs at least one commit
        Path("test-file").touch()
        sp.call(["git", "add", "test-file"])
        sp.call(["git", "commit", "-m", "test commit"])
    return {"vc": vc, "dir": temp_dir}


def test_test_repo(test_repo):
    test_vc_dir = test_repo["dir"] / ".{}".format(test_repo["vc"])
    assert test_vc_dir.is_dir()
    if test_repo["vc"] == "git":
        test_file = test_repo["dir"] / "test-file"
        assert test_file.exists()


def test_no_repo(xonsh_builtins, tmpdir):
    xonsh_builtins.__xonsh__.env = Env(VC_BRANCH_TIMEOUT=2, PWD=tmpdir)
    assert vc.get_hg_branch() is None
    assert vc.get_git_branch() is None


def test_vc_get_branch(test_repo, xonsh_builtins):
    xonsh_builtins.__xonsh__.env = Env(VC_BRANCH_TIMEOUT=2, PWD=test_repo["dir"])
    # get corresponding function from vc module
    get_branch = "get_{}_branch".format(test_repo["vc"])
    branch = getattr(vc, get_branch)()

    assert branch in VC_BRANCH[test_repo["vc"]]
    if test_repo["vc"] == "git":
        git_config = test_repo["dir"] / ".git/config"
        with git_config.open("a") as f:
            f.write(
                """
[color]
branch = always
interactive = always
[color "branch"]
current = yellow reverse
"""
            )

        branch = getattr(vc, get_branch)()
        assert branch in VC_BRANCH[test_repo["vc"]]
        assert not branch.startswith(u"\u001b[")


def test_current_branch_calls_locate_binary_for_empty_cmds_cache(xonsh_builtins):
    cache = xonsh_builtins.__xonsh__.commands_cache
    xonsh_builtins.__xonsh__.env = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache.is_empty = Mock(return_value=True)
    cache.locate_binary = Mock(return_value="")
    vc.current_branch()
    assert cache.locate_binary.called


def test_current_branch_does_not_call_locate_binary_for_non_empty_cmds_cache(
    xonsh_builtins,
):
    cache = xonsh_builtins.__xonsh__.commands_cache
    xonsh_builtins.__xonsh__.env = DummyEnv(VC_BRANCH_TIMEOUT=1)
    cache.is_empty = Mock(return_value=False)
    cache.locate_binary = Mock(return_value="")
    # make lazy locate return nothing to avoid running vc binaries
    cache.lazy_locate_binary = Mock(return_value="")
    vc.current_branch()
    assert not cache.locate_binary.called


def test_dirty_working_directory(test_repo, xonsh_builtins):
    get_dwd = "{}_dirty_working_directory".format(test_repo["vc"])
    xonsh_builtins.__xonsh__.env = Env(VC_BRANCH_TIMEOUT=2, PWD=test_repo["dir"])

    # By default, git / hg do not care about untracked files
    Path("second-test-file").touch()
    assert not getattr(vc, get_dwd)()

    sp.call([test_repo["vc"], "add", "second-test-file"])
    assert getattr(vc, get_dwd)()


@pytest.mark.parametrize("include_untracked", [True, False])
def test_git_dirty_working_directory_includes_untracked(
    xonsh_builtins, test_repo, include_untracked
):
    xonsh_builtins.__xonsh__.env = DummyEnv(VC_GIT_INCLUDE_UNTRACKED=include_untracked)
    if test_repo["vc"] != "git":
        return

    Path("untracked-test-file").touch()
    assert vc.git_dirty_working_directory() == include_untracked
