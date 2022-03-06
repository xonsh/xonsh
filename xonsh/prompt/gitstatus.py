"""Informative git status prompt formatter.

Each part of the status field is extendable and customizable.
"""

import contextlib
import os
import subprocess

from xonsh.prompt.base import PromptFld, PromptFields, MultiPromptFld


def _check_output(xsh, *args: str, **kwargs) -> str:
    denv = xsh.env.detype()
    denv.update({"GIT_OPTIONAL_LOCKS": "0"})

    kwargs.update(
        dict(
            env=denv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
    )
    timeout = xsh.env["VC_BRANCH_TIMEOUT"]
    # See https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
    with subprocess.Popen(args, **kwargs) as proc:
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


class _GSField(PromptFld):
    """wrap output from git command to value"""

    _args = ()

    def update(self, ctx):
        self.value = _check_output(ctx.xsh, *self._args).strip()


gs_hash = _GSField(prefix=":", _args=("git", "rev-parse", "--short", "HEAD"))
gs_tag = _GSField(_args=("git", "describe", "--always"))


@PromptFld.wrap()
def gs_tag_or_hash(fld: PromptFld, ctx):
    fld.value = ctx.pick(gs_tag) or ctx.pick(gs_hash)


def _parse_int(val: str, default=0):
    if val.isdigit():
        return int(val)
    return default


class _GitDir(_GSField):
    _args = ("git", "rev-parse", "--git-dir")
    _cwd = ""

    def update(self, ctx):
        # call the subprocess only if cwd changed
        from xonsh.dirstack import _get_cwd

        cwd = _get_cwd()
        if cwd != self._cwd:
            self._cwd = cwd
            super().update(ctx)


gs_dir = _GitDir()


def get_stash_count(gitdir: str):
    with contextlib.suppress(OSError):
        with open(os.path.join(gitdir, "logs/refs/stash")) as f:
            return sum(1 for _ in f)
    return 0


@PromptFld.wrap(prefix="⚑")
def gs_stash_count(fld: PromptFld, ctx: PromptFields):
    gitdir = ctx.pick(gs_dir).value
    fld.value = get_stash_count(gitdir)


def get_operations(gitdir: str):
    for file, name in (
        ("rebase-merge", "REBASE"),
        ("rebase-apply", "AM/REBASE"),
        ("MERGE_HEAD", "MERGING"),
        ("CHERRY_PICK_HEAD", "CHERRY-PICKING"),
        ("REVERT_HEAD", "REVERTING"),
        ("BISECT_LOG", "BISECTING"),
    ):
        if os.path.exists(os.path.join(gitdir, file)):
            yield name


@PromptFld.wrap(prefix="{CYAN}", separator="|")
def gs_operations(fld, ctx: PromptFields) -> None:
    gitdir = ctx.pick(gs_dir).value
    op = fld.separator.join(get_operations(gitdir))
    if op:
        fld.value = fld.separator + op


@PromptFld.wrap()
def gs_porcelain(fld, ctx: PromptFields) -> None:
    status = _check_output(ctx.xsh, "git", "status", "--porcelain", "--branch")
    branch = ""
    ahead, behind = 0, 0
    untracked, changed, deleted, conflicts, staged = 0, 0, 0, 0, 0
    for line in status.splitlines():
        if line.startswith("##"):
            line = line[2:].strip()
            if "Initial commit on" in line:
                branch = line.split()[-1]
            elif "no branch" in line:
                branch = ctx.pick(gs_tag_or_hash)
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

    fld.value = {
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "untracked": untracked,
        "changed": changed,
        "deleted": deleted,
        "conflicts": conflicts,
        "staged": staged,
    }


class _GSInfo(PromptFld):
    """Return parsed values from ``git status``"""

    info: str

    def update(self, ctx: PromptFields) -> None:
        info = ctx.pick(gs_porcelain).value
        self.value = info[self.info]


gs_branch = _GSInfo(prefix="{CYAN}", info="branch")
gs_ahead = _GSInfo(prefix="↑·", info="ahead")
gs_behind = _GSInfo(prefix="↓·", info="behind")
gs_untracked = _GSInfo(prefix="…", info="untracked")
gs_changed = _GSInfo(prefix="{BLUE}+", suffix="{RESET}", info="changed")
gs_deleted = _GSInfo(prefix="{RED}-", suffix="{RESET}", info="deleted")
gs_conflicts = _GSInfo(prefix="{RED}×", suffix="{RESET}", info="conflicts")
gs_staged = _GSInfo(prefix="{RED}●", suffix="{RESET}", info="staged")


@PromptFld.wrap()
def gs_numstat(fld, ctx):
    changed = _check_output(ctx.xsh, "git", "diff", "--numstat")

    insert = 0
    delete = 0

    if changed:
        for line in changed.splitlines():
            x = line.split(maxsplit=2)
            if len(x) > 1:
                insert += _parse_int(x[0])
                delete += _parse_int(x[1])
    fld.value = (insert, delete)


@PromptFld.wrap(prefix="{BLUE}+", suffix="{RESET}")
def gs_lines_added(fld: PromptFld, ctx: PromptFields):
    fld.value = ctx.pick(gs_numstat).value[0]


@PromptFld.wrap(prefix="{RED}-", suffix="{RESET}")
def gs_lines_removed(fld: PromptFld, ctx):
    fld.value = ctx.pick(gs_numstat).value[-1]


@PromptFld.wrap(prefix="{BOLD_GREEN}", suffix="{RESET}", symbol="✓")
def gs_clean(fld, ctx):
    changes = sum(
        (
            ctx.pick(f).value
            for f in (
                gs_staged,
                gs_conflicts,
                gs_changed,
                gs_deleted,
                gs_untracked,
                gs_stash_count,
            )
        )
    )
    if not changes:
        fld.value = fld.symbol


gitstatus = MultiPromptFld(
    gs_branch,
    gs_ahead,
    gs_behind,
    gs_operations,
    "{RESET}|",
    gs_staged,
    gs_conflicts,
    gs_changed,
    gs_deleted,
    gs_untracked,
    gs_stash_count,
    gs_lines_added,
    gs_lines_removed,
    gs_clean,
)
"""Return str `BRANCH|OPERATOR|numbers`"""
