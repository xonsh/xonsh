"""Prompt formatter for simple version control branches"""

# pylint:disable=no-member, invalid-name
import contextlib
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading

import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.lib.lazyasd import LazyObject
from xonsh.procs.executables import locate_executable

RE_REMOVE_ANSI = LazyObject(
    lambda: re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]"),
    globals(),
    "RE_REMOVE_ANSI",
)


def _run_git_cmd(cmd):
    # create a safe detyped env dictionary and update with the additional git environment variables
    # when running git status commands we do not want to acquire locks running command like git status
    denv = dict(XSH.env.detype())
    denv.update({"GIT_OPTIONAL_LOCKS": "0"})
    return subprocess.check_output(cmd, env=denv, stderr=subprocess.DEVNULL)


def _get_git_branch(q):
    # from https://git-blame.blogspot.com/2013/06/checking-current-branch-programatically.html
    for cmds in [
        "git symbolic-ref --short HEAD",
        "git show-ref --head -s --abbrev",  # in detached mode return sha1
    ]:
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            branch = xt.decode_bytes(_run_git_cmd(cmds.split()))
            if branch:
                q.put(branch.splitlines()[0])
                return
    # all failed
    q.put(None)


def get_git_branch():
    """Attempts to find the current git branch. If this could not
    be determined (timeout, not in a git repo, etc.) then this returns None.
    """
    branch = None
    timeout = XSH.env.get("VC_BRANCH_TIMEOUT")
    q = queue.Queue()

    t = threading.Thread(target=_get_git_branch, args=(q,))
    t.start()
    t.join(timeout=timeout)
    try:
        branch = q.get_nowait()
        if branch:
            branch = RE_REMOVE_ANSI.sub("", branch)
    except queue.Empty:
        branch = None
    return branch


def _get_hg_root(q):
    _curpwd = XSH.env["PWD"]
    while True:
        if not os.path.isdir(_curpwd):
            return False
        try:
            dot_hg_is_in_curwd = any([b.name == ".hg" for b in os.scandir(_curpwd)])
        except OSError:
            return False
        if dot_hg_is_in_curwd:
            q.put(_curpwd)
            break
        else:
            _oldpwd = _curpwd
            _curpwd = os.path.split(_curpwd)[0]
            if _oldpwd == _curpwd:
                return False


def get_hg_branch(root=None):
    """Try to get the mercurial branch of the current directory,
    return None if not in a repo or subprocess.TimeoutExpired if timed out.
    """
    env = XSH.env
    timeout = env["VC_BRANCH_TIMEOUT"]
    q = queue.Queue()
    t = threading.Thread(target=_get_hg_root, args=(q,))
    t.start()
    t.join(timeout=timeout)
    try:
        root = pathlib.Path(q.get_nowait())
    except queue.Empty:
        return None
    if env.get("VC_HG_SHOW_BRANCH"):
        # get branch name
        branch_path = root / ".hg" / "branch"
        if branch_path.exists():
            with open(branch_path) as branch_file:
                branch = branch_file.read().strip()
        else:
            branch = "default"
    else:
        branch = ""
    # add activated bookmark and topic
    for filename in ["bookmarks.current", "topic"]:
        feature_branch_path = root / ".hg" / filename
        if feature_branch_path.exists():
            with open(feature_branch_path) as file:
                feature_branch = file.read().strip()
            if feature_branch:
                if branch:
                    if filename == "topic":
                        branch = f"{branch}/{feature_branch}"
                    else:
                        branch = f"{branch}, {feature_branch}"
                else:
                    branch = feature_branch

    return branch


def _run_fossil_cmd(cmd):
    timeout = XSH.env.get("VC_BRANCH_TIMEOUT")
    result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)
    return result


def get_fossil_branch():
    """Attempts to find the current fossil branch. If this could not
    be determined (timeout, not in a fossil checkout, etc.) then this returns None.
    """
    # from fossil branch --help: "fossil branch current: Print the name of the branch for the current check-out"
    cmd = "fossil branch current".split()
    try:
        branch = xt.decode_bytes(_run_fossil_cmd(cmd))
    except (subprocess.CalledProcessError, OSError):
        branch = None
    else:
        branch = RE_REMOVE_ANSI.sub("", branch.splitlines()[0])
    return branch


_FIRST_BRANCH_TIMEOUT = True


def _first_branch_timeout_message():
    global _FIRST_BRANCH_TIMEOUT
    sbtm = XSH.env["SUPPRESS_BRANCH_TIMEOUT_MESSAGE"]
    if not _FIRST_BRANCH_TIMEOUT or sbtm:
        return
    _FIRST_BRANCH_TIMEOUT = False
    print(
        "xonsh: branch timeout: computing the branch name, color, or both "
        "timed out while formatting the prompt. You may avoid this by "
        "increasing the value of $VC_BRANCH_TIMEOUT or by removing branch "
        "fields, like {curr_branch}, from your $PROMPT. See the FAQ "
        "for more details. This message will be suppressed for the remainder "
        "of this session. To suppress this message permanently, set "
        "$SUPPRESS_BRANCH_TIMEOUT_MESSAGE = True in your xonshrc file.",
        file=sys.stderr,
    )


def _vc_has(binary):
    """This allows us to locate binaries after git only if necessary"""
    return bool(locate_executable(binary))


def current_branch():
    """Gets the branch for a current working directory. Returns an empty string
    if the cwd is not a repository.  This currently only works for git, hg, and fossil
    and should be extended in the future.  If a timeout occurred, the string
    '<branch-timeout>' is returned.
    """
    branch = None
    if _vc_has("git"):
        branch = get_git_branch()
    if not branch and _vc_has("hg"):
        branch = get_hg_branch()
    if not branch and _vc_has("fossil"):
        branch = get_fossil_branch()
    if isinstance(branch, subprocess.TimeoutExpired):
        branch = "<branch-timeout>"
        _first_branch_timeout_message()
    return branch or None


def _git_dirty_working_directory(q, include_untracked):
    try:
        cmd = ["git", "status", "--porcelain"]
        if include_untracked:
            cmd += ["--untracked-files=normal"]
        else:
            cmd += ["--untracked-files=no"]
        status = _run_git_cmd(cmd)
        if status is not None:
            q.put(bool(status))
        else:
            q.put(None)
    except (subprocess.CalledProcessError, OSError):
        q.put(None)


def git_dirty_working_directory():
    """Returns whether or not the git directory is dirty. If this could not
    be determined (timeout, file not found, etc.) then this returns None.
    """
    env = XSH.env
    timeout = env.get("VC_BRANCH_TIMEOUT")
    include_untracked = env.get("VC_GIT_INCLUDE_UNTRACKED")
    q = queue.Queue()
    t = threading.Thread(
        target=_git_dirty_working_directory, args=(q, include_untracked)
    )
    t.start()
    t.join(timeout=timeout)
    try:
        return q.get_nowait()
    except queue.Empty:
        return None


def hg_dirty_working_directory():
    """Computes whether or not the mercurial working directory is dirty or not.
    If this cannot be determined, None is returned.
    """
    env = XSH.env
    cwd = env["PWD"]
    denv = env.detype()
    vcbt = env["VC_BRANCH_TIMEOUT"]
    # Override user configurations settings and aliases
    denv["HGRCPATH"] = ""
    try:
        s = subprocess.check_output(
            ["hg", "identify", "--id"],
            stderr=subprocess.PIPE,
            cwd=cwd,
            timeout=vcbt,
            text=True,
            env=denv,
        )
        return s.strip(os.linesep).endswith("+")
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return None


def fossil_dirty_working_directory():
    """Returns whether the fossil checkout is dirty. If this could not
    be determined (timeout, file not found, etc.) then this returns None.
    """
    cmd = ["fossil", "changes"]
    try:
        status = _run_fossil_cmd(cmd)
    except (subprocess.CalledProcessError, OSError):
        status = None
    else:
        status = bool(status)
    return status


def dirty_working_directory():
    """Returns a boolean as to whether there are uncommitted files in version
    control repository we are inside. If this cannot be determined, returns
    None. Currently supports git and hg.
    """
    dwd = None
    if _vc_has("git"):
        dwd = git_dirty_working_directory()
    if dwd is None and _vc_has("hg"):
        dwd = hg_dirty_working_directory()
    if dwd is None and _vc_has("fossil"):
        dwd = fossil_dirty_working_directory()
    return dwd


def branch_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are bold, intense colors
    for the foreground.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = "{BOLD_INTENSE_YELLOW}"
    elif dwd:
        color = "{BOLD_INTENSE_RED}"
    else:
        color = "{BOLD_INTENSE_GREEN}"
    return color


def branch_bg_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are background colors.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = "{BACKGROUND_YELLOW}"
    elif dwd:
        color = "{BACKGROUND_RED}"
    else:
        color = "{BACKGROUND_GREEN}"
    return color
