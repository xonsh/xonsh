import os
import subprocess as sp
import textwrap
from pathlib import Path

import pytest

from xonsh.prompt import vc

# Xonsh interaction with version control systems.
VC_BRANCH = {
    "git": {"master", "main"},
    "hg": {"default"},
    "fossil": {"trunk"},
}
VC_INIT: dict[str, list[list[str]]] = {
    # A sequence of commands required to initialize a repository
    "git": [["init"]],
    "hg": [["init"]],
    # Fossil "init" creates a central repository file with the given name,
    # "open" creates the working directory at another, arbitrary location.
    "fossil": [["init", "test.fossil"], ["open", "test.fossil"]],
}


@pytest.fixture(params=VC_BRANCH.keys())
def repo(request, tmpdir_factory):
    """Return a dict with vc and a temporary dir
    that is a repository for testing.
    """
    vc = request.param
    temp_dir = Path(tmpdir_factory.mktemp("dir"))
    os.chdir(temp_dir)
    try:
        for init_command in VC_INIT[vc]:
            sp.call([vc] + init_command)
    except FileNotFoundError:
        pytest.skip(f"cannot find {vc} executable")
    if vc == "git":
        _init_git_repository(temp_dir)
    return {"vc": vc, "dir": temp_dir}


def _init_git_repository(temp_dir):
    git_config = temp_dir / ".git/config"
    git_config.write_text(
        textwrap.dedent(
            """\
        [user]
        name = me
        email = my@email.address
        [init]
        defaultBranch = main
        """
        )
    )
    # git needs at least one commit
    Path("test-file").touch()
    sp.call(["git", "add", "test-file"])
    sp.call(["git", "commit", "-m", "test commit"])


@pytest.fixture
def set_xenv(xession, monkeypatch):
    def _wrapper(path):
        xession.env.update(dict(VC_BRANCH_TIMEOUT=2, PWD=path))
        return xession

    return _wrapper


def test_test_repo(repo):
    if repo["vc"] == "fossil":
        # Fossil stores the check-out meta-data in a special file within the open check-out.
        # At least one of these below must exist
        metadata_file_names = {
            ".fslckout",
            "_FOSSIL_",
        }  # .fslckout on Unix, _FOSSIL_ on Windows
        existing_files = {file.name for file in repo["dir"].iterdir()}
        assert existing_files.intersection(metadata_file_names)
    else:
        test_vc_dir = repo["dir"] / ".{}".format(repo["vc"])
        assert test_vc_dir.is_dir()
    if repo["vc"] == "git":
        test_file = repo["dir"] / "test-file"
        assert test_file.exists()


def test_no_repo(tmpdir, set_xenv):
    set_xenv(tmpdir)
    assert vc.get_hg_branch() is None
    assert vc.get_git_branch() is None


def test_vc_get_branch(repo, set_xenv):
    set_xenv(repo["dir"])
    # get corresponding function from vc module
    get_branch = "get_{}_branch".format(repo["vc"])
    branch = getattr(vc, get_branch)()

    assert branch in VC_BRANCH[repo["vc"]]
    if repo["vc"] == "git":
        git_config = repo["dir"] / ".git/config"
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
        assert branch in VC_BRANCH[repo["vc"]]
        assert not branch.startswith("\u001b[")


def test_dirty_working_directory(repo, set_xenv):
    get_dwd = "{}_dirty_working_directory".format(repo["vc"])
    set_xenv(repo["dir"])

    # By default, git / hg do not care about untracked files
    Path("second-test-file").touch()
    assert not getattr(vc, get_dwd)()

    sp.call([repo["vc"], "add", "second-test-file"])
    assert getattr(vc, get_dwd)()


@pytest.mark.parametrize("include_untracked", [True, False])
def test_git_dirty_working_directory_includes_untracked(
    xession, fake_process, include_untracked
):
    xession.env["VC_GIT_INCLUDE_UNTRACKED"] = include_untracked

    if include_untracked:
        fake_process.register_subprocess(
            command="git status --porcelain --untracked-files=normal".split(),
            stdout=b"?? untracked-test-file",
        )
    else:
        fake_process.register_subprocess(
            command="git status --porcelain --untracked-files=no".split(),
            stdout=b"",
        )

    assert vc.git_dirty_working_directory() == include_untracked
