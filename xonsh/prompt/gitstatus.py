# -*- coding: utf-8 -*-
"""Informative git status prompt formatter"""
import os
import subprocess

from xonsh.built_ins import XSH
from xonsh.color_tools import COLORS
from xonsh.tools import NamedConstantMeta, XAttr


def _check_output(*args, **kwargs) -> str:
    denv = XSH.env.detype()
    denv.update({"GIT_OPTIONAL_LOCKS": "0"})

    kwargs.update(
        dict(
            env=denv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
    )
    timeout = XSH.env["VC_BRANCH_TIMEOUT"]
    # See https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
    with subprocess.Popen(*args, **kwargs) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    proc.returncode, proc.args, output=out, stderr=err
                )  # note err will always be empty as we redirect stderr to DEVNULL abvoe
            return out
        except subprocess.TimeoutExpired:
            # We use `.terminate()` (SIGTERM) instead of `.kill()` (SIGKILL) here
            # because otherwise we guarantee that a `.git/index.lock` file will be
            # left over, and subsequent git operations will fail.
            # We don't want that.
            # As a result, we must rely on git to exit properly on SIGTERM.
            proc.terminate()
            # We wait() to ensure that git has finished before the next
            # `gitstatus` prompt is rendered (otherwise `index.lock` still exists,
            # and it will fail).
            # We don't technically have to call `wait()` here as the
            # `with subprocess.Popen()` context manager above would do that
            # for us, but we do it to be explicit that waiting is being done.
            proc.wait()  # we ignore what git says after we sent it SIGTERM
            raise


class _DEFS(metaclass=NamedConstantMeta):
    HASH_INDICATOR = XAttr(":")
    BRANCH = XAttr("{CYAN}")
    OPERATION = XAttr("{CYAN}")
    STAGED = XAttr("{RED}●")
    CONFLICTS = XAttr("{RED}×")
    CHANGED = XAttr("{BLUE}+")
    DELETED = XAttr("{RED}-")
    UNTRACKED = XAttr("…")
    STASHED = XAttr("⚑")
    CLEAN = XAttr("{BOLD_GREEN}✓")
    AHEAD = XAttr("↑·")
    BEHIND = XAttr("↓·")
    LINES_ADDED = XAttr("{BLUE}+")
    LINES_REMOVED = XAttr("{RED}-")
    SEPARATOR = XAttr("{RESET}|")


def _get_def(attr: XAttr) -> str:
    key = attr.name.upper()
    def_ = XSH.env.get("XONSH_GITSTATUS_" + key)
    return def_ if def_ is not None else attr.value


def _is_hidden(attr: XAttr) -> bool:
    hidden = XSH.env.get("XONSH_GITSTATUS_FIELDS_HIDDEN") or set()
    return attr.name.upper() in hidden or attr.name.lower() in hidden


def _get_tag_or_hash() -> str:
    tag_or_hash = _check_output(["git", "describe", "--always"]).strip()
    hash_ = _check_output(["git", "rev-parse", "--short", "HEAD"]).strip()
    have_tag_name = tag_or_hash != hash_
    return tag_or_hash if have_tag_name else _get_def(_DEFS.HASH_INDICATOR) + hash_


def _parse_int(val: str, default=0):
    if val.isdigit():
        return int(val)
    return default


def _get_files_changed():
    try:
        changed = _check_output(["git", "diff", "--numstat"])
    except subprocess.CalledProcessError:
        return {}

    insert = 0
    delete = 0

    if changed:
        for line in changed.splitlines():
            x = line.split(maxsplit=2)
            if len(x) > 1:
                insert += _parse_int(x[0])
                delete += _parse_int(x[1])

    return {_DEFS.LINES_ADDED: insert, _DEFS.LINES_REMOVED: delete}


def _get_stash(gitdir):
    try:
        with open(os.path.join(gitdir, "logs/refs/stash")) as f:
            return sum(1 for _ in f)
    except IOError:
        return 0


def _gitoperation(gitdir):
    files = (
        ("rebase-merge", "REBASE"),
        ("rebase-apply", "AM/REBASE"),
        ("MERGE_HEAD", "MERGING"),
        ("CHERRY_PICK_HEAD", "CHERRY-PICKING"),
        ("REVERT_HEAD", "REVERTING"),
        ("BISECT_LOG", "BISECTING"),
    )
    operations = [f[1] for f in files if os.path.exists(os.path.join(gitdir, f[0]))]
    if operations:
        return "|" + "|".join(operations)
    return ""


def _get_operation_stashed():
    gitdir = _check_output(["git", "rev-parse", "--git-dir"]).strip()
    stashed = _get_stash(gitdir)
    operation = _gitoperation(gitdir)
    return {_DEFS.OPERATION: operation, _DEFS.STASHED: stashed}


def _get_status_fields():
    """Return parsed values from ``git status``"""

    status = _check_output(["git", "status", "--porcelain", "--branch"])
    branch = ""
    ahead, behind = 0, 0
    untracked, changed, deleted, conflicts, staged = 0, 0, 0, 0, 0
    for line in status.splitlines():
        if line.startswith("##"):
            line = line[2:].strip()
            if "Initial commit on" in line:
                branch = line.split()[-1]
            elif "no branch" in line:
                branch = _get_tag_or_hash()
            elif "..." not in line:
                branch = line
            else:
                branch, rest = line.split("...")
                if " " in rest:
                    divergence = rest.split(" ", 1)[-1]
                    divergence = divergence.strip("[]")
                    for div in divergence.split(", "):
                        if "ahead" in div:
                            ahead = int(div[len("ahead ") :].strip())
                        elif "behind" in div:
                            behind = int(div[len("behind ") :].strip())
        elif line.startswith("??"):
            untracked += 1
        else:
            if len(line) > 1:
                if line[1] == "M":
                    changed += 1
                elif line[1] == "D":
                    deleted += 1
            if len(line) > 0 and line[0] == "U":
                conflicts += 1
            elif len(line) > 0 and line[0] != " ":
                staged += 1

    return {
        _DEFS.BRANCH: branch,
        _DEFS.AHEAD: ahead,
        _DEFS.BEHIND: behind,
        _DEFS.UNTRACKED: untracked,
        _DEFS.CHANGED: changed,
        _DEFS.DELETED: deleted,
        _DEFS.CONFLICTS: conflicts,
        _DEFS.STAGED: staged,
    }


def get_gitstatus_fields():
    """return all shown fields"""
    fields = {}
    for keys, provider in (
        (
            (
                _DEFS.BRANCH,
                _DEFS.AHEAD,
                _DEFS.BEHIND,
                _DEFS.UNTRACKED,
                _DEFS.CHANGED,
                _DEFS.DELETED,
                _DEFS.CONFLICTS,
                _DEFS.STAGED,
            ),
            _get_status_fields,
        ),
        (
            (
                _DEFS.OPERATION,
                _DEFS.STASHED,
            ),
            _get_operation_stashed,
        ),
        (
            (
                _DEFS.LINES_ADDED,
                _DEFS.LINES_REMOVED,
            ),
            _get_files_changed,
        ),
    ):
        if any(map(lambda x: not _is_hidden(x), keys)):
            try:
                fields.update(provider())
            except subprocess.SubprocessError:
                return None
    return fields


def gitstatus_prompt():
    """Return str `BRANCH|OPERATOR|numbers`"""
    fields = get_gitstatus_fields()
    if fields is None:
        return None

    ret = ""
    for fld in (_DEFS.BRANCH, _DEFS.AHEAD, _DEFS.BEHIND, _DEFS.OPERATION):
        if not _is_hidden(fld):
            val = fields[fld]
            if not val:
                continue
            ret += _get_def(fld) + str(val)

    if ret:
        ret += "|"

    number_flds = (
        _DEFS.STAGED,
        _DEFS.CONFLICTS,
        _DEFS.CHANGED,
        _DEFS.DELETED,
        _DEFS.UNTRACKED,
        _DEFS.STASHED,
        _DEFS.LINES_ADDED,
        _DEFS.LINES_REMOVED,
    )
    for fld in number_flds:
        if _is_hidden(fld):
            continue
        symbol = _get_def(fld)
        value = fields[fld]
        if symbol and value > 0:
            ret += symbol + str(value) + COLORS.RESET
    if sum((fields.get(fld, 0) for fld in number_flds)) == 0 and not _is_hidden(
        _DEFS.CLEAN
    ):
        symbol = _get_def(_DEFS.CLEAN)
        if symbol:
            ret += symbol + COLORS.RESET
    ret = ret.rstrip("|")

    if not ret.endswith(COLORS.RESET):
        ret += COLORS.RESET

    ret = ret.replace("|", _get_def(_DEFS.SEPARATOR))

    return ret
