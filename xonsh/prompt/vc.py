# -*- coding: utf-8 -*-
"""Prompt formatter for simple version control branchs"""
# pylint:disable=no-member, invalid-name

import os
import sys
import queue
import builtins
import threading
import subprocess

import xonsh.tools as xt


def _get_git_branch(q):
    try:
        branches = xt.decode_bytes(subprocess.check_output(
            ['git', 'branch'],
            stderr=subprocess.DEVNULL
        )).splitlines()
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        q.put(None)
    else:
        for branch in branches:
            if not branch.startswith('* '):
                continue
            elif branch.endswith(')'):
                branch = branch.split()[-1][:-1]
            else:
                branch = branch.split()[-1]

            q.put(branch)
            break
        else:
            q.put(None)


def get_git_branch():
    """Attempts to find the current git branch. If this could not
    be determined (timeout, not in a git repo, etc.) then this returns None.
    """
    branch = None
    timeout = builtins.__xonsh_env__.get('VC_BRANCH_TIMEOUT')
    q = queue.Queue()

    t = threading.Thread(target=_get_git_branch, args=(q,))
    t.start()
    t.join(timeout=timeout)
    try:
        branch = q.get_nowait()
    except queue.Empty:
        branch = None
    return branch


def get_hg_branch(root=None):
    """Try to get the mercurial branch of the current directory,
    return None if not in a repo or subprocess.TimeoutExpired if timed out.
    """
    env = builtins.__xonsh_env__
    hg_binary = env['VC_HG_BINARY']
    timeout = env['VC_BRANCH_TIMEOUT']
    try:
        root = subprocess.check_output([hg_binary, 'root'], timeout=timeout,
                                       stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return subprocess.TimeoutExpired([hg_binary], timeout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # not in repo or command not in PATH
        return None
    else:
        root = xt.decode_bytes(root).strip()
    if env.get('VC_HG_SHOW_BRANCH'):
        # get branch name
        branch_path = os.path.sep.join([root, '.hg', 'branch'])
        if os.path.exists(branch_path):
            with open(branch_path, 'r') as branch_file:
                branch = branch_file.read()
        else:
            branch = 'default'
    else:
        branch = ''
    # add bookmark, if we can
    bookmark_path = os.path.sep.join([root, '.hg', 'bookmarks.current'])
    if os.path.exists(bookmark_path):
        with open(bookmark_path, 'r') as bookmark_file:
            active_bookmark = bookmark_file.read()
        if env.get('VC_HG_SHOW_BRANCH') is True:
            branch = "{0}, {1}".format(*(b.strip(os.linesep) for b in
                                         (branch, active_bookmark)))
        else:
            branch = active_bookmark.strip(os.linesep)
    else:
        branch = branch.strip(os.linesep)
    return branch


_FIRST_BRANCH_TIMEOUT = True


def _first_branch_timeout_message():
    global _FIRST_BRANCH_TIMEOUT
    sbtm = builtins.__xonsh_env__['SUPPRESS_BRANCH_TIMEOUT_MESSAGE']
    if not _FIRST_BRANCH_TIMEOUT or sbtm:
        return
    _FIRST_BRANCH_TIMEOUT = False
    print('xonsh: branch timeout: computing the branch name, color, or both '
          'timed out while formatting the prompt. You may avoid this by '
          'increasing the value of $VC_BRANCH_TIMEOUT or by removing branch '
          'fields, like {curr_branch}, from your $PROMPT. See the FAQ '
          'for more details. This message will be suppressed for the remainder '
          'of this session. To suppress this message permanently, set '
          '$SUPPRESS_BRANCH_TIMEOUT_MESSAGE = True in your xonshrc file.',
          file=sys.stderr)


def current_branch():
    """Gets the branch for a current working directory. Returns an empty string
    if the cwd is not a repository.  This currently only works for git and hg
    and should be extended in the future.  If a timeout occurred, the string
    '<branch-timeout>' is returned.
    """
    branch = None
    cmds = builtins.__xonsh_commands_cache__
    env = builtins.__xonsh_env__
    hg_binary = env['VC_HG_BINARY']
    # check for binary only once
    if cmds.is_empty():
        has_git = bool(cmds.locate_binary('git'))
        has_hg = bool(cmds.locate_binary(hg_binary))
    else:
        has_git = bool(cmds.lazy_locate_binary('git'))
        has_hg = bool(cmds.lazy_locate_binary(hg_binary))
    if has_git:
        branch = get_git_branch()
    if not branch and has_hg:
        branch = get_hg_branch()
    if isinstance(branch, subprocess.TimeoutExpired):
        branch = '<branch-timeout>'
        _first_branch_timeout_message()
    return branch or None


def _git_dirty_working_directory(q, include_untracked):
    status = None
    try:
        cmd = ['git', 'status', '--porcelain']
        if include_untracked:
            cmd.append('--untracked-files=normal')
        else:
            cmd.append('--untracked-files=no')
        status = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        q.put(None)
    if status is not None:
        return q.put(bool(status))


def git_dirty_working_directory(include_untracked=False):
    """Returns whether or not the git directory is dirty. If this could not
    be determined (timeout, file not found, etc.) then this returns None.
    """
    timeout = builtins.__xonsh_env__.get("VC_BRANCH_TIMEOUT")
    q = queue.Queue()
    t = threading.Thread(target=_git_dirty_working_directory,
                         args=(q, include_untracked))
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
    env = builtins.__xonsh_env__
    cwd = env['PWD']
    denv = env.detype()
    vcbt = env['VC_BRANCH_TIMEOUT']
    hg_binary = env['VC_HG_BINARY']
    # Override user configurations settings and aliases
    denv['HGRCPATH'] = ''
    try:
        s = subprocess.check_output([hg_binary, 'identify', '--id'],
                                    stderr=subprocess.PIPE, cwd=cwd,
                                    timeout=vcbt, universal_newlines=True,
                                    env=denv)
        return s.strip(os.linesep).endswith('+')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return None


def dirty_working_directory():
    """Returns a boolean as to whether there are uncommitted files in version
    control repository we are inside. If this cannot be determined, returns
    None. Currently supports git and hg.
    """
    dwd = None
    cmds = builtins.__xonsh_commands_cache__
    env = builtins.__xonsh_env__
    hg_binary = env['VC_HG_BINARY']
    if cmds.lazy_locate_binary('git'):
        dwd = git_dirty_working_directory()
    if cmds.lazy_locate_binary(hg_binary) and dwd is None:
        dwd = hg_dirty_working_directory()
    return dwd


def branch_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are bold, intense colors
    for the foreground.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = '{BOLD_INTENSE_YELLOW}'
    elif dwd:
        color = '{BOLD_INTENSE_RED}'
    else:
        color = '{BOLD_INTENSE_GREEN}'
    return color


def branch_bg_color():
    """Return red if the current branch is dirty, yellow if the dirtiness can
    not be determined, and green if it clean. These are bacground colors.
    """
    dwd = dirty_working_directory()
    if dwd is None:
        color = '{BACKGROUND_YELLOW}'
    elif dwd:
        color = '{BACKGROUND_RED}'
    else:
        color = '{BACKGROUND_GREEN}'
    return color
