"""Informative git status prompt formatter.

Each part of the status field is extendable and customizable.

Following fields are available other than ``gitstatus``

* gitstatus.ahead
* gitstatus.behind
* gitstatus.branch
* gitstatus.changed
* gitstatus.clean
* gitstatus.conflicts
* gitstatus.deleted
* gitstatus.lines_added
* gitstatus.lines_removed
* gitstatus.numstat
* gitstatus.operations
* gitstatus.porcelain
* gitstatus.repo_path
* gitstatus.short_head
* gitstatus.staged
* gitstatus.stash_count
* gitstatus.tag
* gitstatus.tag_or_hash
* gitstatus.untracked

All the fields have prefix and suffix attribute that can be set in the configuration as shown below.
Other attributes can also be changed.

See some examples below,

.. code-block:: xonsh

    from xonsh.prompt.base import PromptField, PromptFields

    # 1. to change the color of the branch name
    $PROMPT_FIELDS['gitstatus.branch'].prefix = "{RED}"

    # 2. to change the symbol for conflicts from ``{RED}×``
    $PROMPT_FIELDS['gitstatus.conflicts'].prefix = "{GREEN}*"

    # 3. hide the branch name if it is main or dev
    branch_field = $PROMPT_FIELDS['gitstatus.branch']
    old_updator = branch_field.updator
    def new_updator(fld: PromptField, ctx: PromptFields):
        old_updator(fld, ctx)
        if fld.value in {"main", "dev"}:
            fld.value = ""
    branch_field.updator = new_updator

"""

import contextlib
import os
import subprocess

from xonsh.prompt.base import MultiPromptField, PromptField, PromptFields


def _get_sp_output(xsh, *args: str, **kwargs) -> str:
    denv = xsh.env.detype()
    denv.update({"GIT_OPTIONAL_LOCKS": "0"})

    kwargs.update(
        dict(
            env=denv,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    )
    timeout = xsh.env["VC_BRANCH_TIMEOUT"]
    out = ""
    # See https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate
    with subprocess.Popen(args, **kwargs) as proc:
        try:
            out, _ = proc.communicate(timeout=timeout)
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
    return out


class _GitDir(PromptField):
    _cwd = ""

    def update(self, ctx):
        # call the subprocess only if cwd changed
        # or if value is None (in case `git init` was run)
        from xonsh.dirstack import _get_cwd

        cwd = _get_cwd()
        if cwd != self._cwd or self.value is None:
            self._cwd = cwd
            self.value = _get_sp_output(
                ctx.xsh, "git", "rev-parse", "--git-dir"
            ).strip()
            if self.value == "":
                self.value = None


repo_path = _GitDir()


def inside_repo(ctx):
    return ctx.pick_val(repo_path) is not None


class GitStatusPromptField(PromptField):
    """Only calls the updator if we are inside a git repository"""

    def update(self, ctx):
        if inside_repo(ctx):
            if self.updator:
                self.updator(self, ctx)
        else:
            self.value = None


class _GSField(GitStatusPromptField):
    """wrap output from git command to value"""

    _args: "tuple[str, ...]" = ()

    def updator(self, fld, ctx):
        self.value = _get_sp_output(ctx.xsh, *self._args).strip()


short_head = _GSField(prefix=":", _args=("git", "rev-parse", "--short", "HEAD"))
tag = _GSField(_args=("git", "describe", "--always"))


@GitStatusPromptField.wrap()
def tag_or_hash(fld: PromptField, ctx):
    fld.value = ctx.pick(tag) or ctx.pick(short_head)


def _parse_int(val: str, default=0):
    if val.isdigit():
        return int(val)
    return default


def get_stash_count(gitdir: str):
    """Get git-stash count"""
    with contextlib.suppress(OSError):
        with open(os.path.join(gitdir, "logs/refs/stash")) as f:
            return sum(1 for _ in f)
    return 0


@GitStatusPromptField.wrap(prefix="⚑")
def stash_count(fld: PromptField, ctx: PromptFields):
    fld.value = get_stash_count(ctx.pick_val(repo_path))


def get_operations(gitdir: str):
    """get the current git operation e.g. MERGE/REBASE..."""
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


@GitStatusPromptField.wrap(prefix="{CYAN}", separator="|")
def operations(fld, ctx: PromptFields) -> None:
    gitdir = ctx.pick_val(repo_path)
    op = fld.separator.join(get_operations(gitdir))
    if op:
        fld.value = fld.separator + op
    else:
        fld.value = ""


@GitStatusPromptField.wrap()
def porcelain(fld, ctx: PromptFields):
    """Return parsed values from ``git status --porcelain``"""

    status = _get_sp_output(ctx.xsh, "git", "status", "--porcelain", "--branch")
    branch = ""
    ahead, behind = 0, 0
    untracked, changed, deleted, conflicts, staged = 0, 0, 0, 0, 0
    for line in status.splitlines():
        if line.startswith("##"):
            line = line[2:].strip()
            if "Initial commit on" in line:
                branch = line.split()[-1]
            elif "no branch" in line:
                branch = ctx.pick(tag_or_hash) or ""
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


def get_gitstatus_info(fld: "_GSInfo", ctx: PromptFields) -> None:
    """Get individual fields from $PROMPT_FIELDS['gitstatus.porcelain']"""
    info = ctx.pick_val(porcelain)
    fld.value = info[fld.info]


class _GSInfo(GitStatusPromptField):
    info: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.updator = get_gitstatus_info


branch = _GSInfo(prefix="{CYAN}", info="branch")
ahead = _GSInfo(prefix="↑·", info="ahead")
behind = _GSInfo(prefix="↓·", info="behind")
untracked = _GSInfo(prefix="…", info="untracked")
changed = _GSInfo(prefix="{BLUE}+", suffix="{RESET}", info="changed")
deleted = _GSInfo(prefix="{RED}-", suffix="{RESET}", info="deleted")
conflicts = _GSInfo(prefix="{RED}×", suffix="{RESET}", info="conflicts")
staged = _GSInfo(prefix="{RED}●", suffix="{RESET}", info="staged")


@GitStatusPromptField.wrap()
def numstat(fld, ctx):
    changed = _get_sp_output(ctx.xsh, "git", "diff", "--numstat")

    insert = 0
    delete = 0

    if changed:
        for line in changed.splitlines():
            x = line.split(maxsplit=2)
            if len(x) > 1:
                insert += _parse_int(x[0])
                delete += _parse_int(x[1])
    fld.value = (insert, delete)


@GitStatusPromptField.wrap(prefix="{BLUE}+", suffix="{RESET}")
def lines_added(fld: PromptField, ctx: PromptFields):
    fld.value = ctx.pick_val(numstat)[0]


@GitStatusPromptField.wrap(prefix="{RED}-", suffix="{RESET}")
def lines_removed(fld: PromptField, ctx):
    fld.value = ctx.pick_val(numstat)[-1]


@GitStatusPromptField.wrap(prefix="{BOLD_GREEN}", suffix="{RESET}", symbol="✓")
def clean(fld, ctx):
    changes = sum(
        ctx.pick_val(f)
        for f in (
            staged,
            conflicts,
            changed,
            deleted,
            untracked,
            stash_count,
        )
    )
    fld.value = "" if changes else fld.symbol


class GitStatus(MultiPromptField):
    """Return str `BRANCH|OPERATOR|numbers`"""

    fragments = (
        ".branch",
        ".ahead",
        ".behind",
        ".operations",
        "{RESET}|",
        ".staged",
        ".conflicts",
        ".changed",
        ".deleted",
        ".untracked",
        ".stash_count",
        ".lines_added",
        ".lines_removed",
        ".clean",
    )
    hidden = (
        ".lines_added",
        ".lines_removed",
    )
    """These fields will not be processed for the result"""

    def get_frags(self, env):
        for frag in self.fragments:
            if frag in self.hidden:
                continue
            yield frag

    def update(self, ctx):
        if inside_repo(ctx):
            super().update(ctx)
        else:
            self.value = None


gitstatus = GitStatus()
