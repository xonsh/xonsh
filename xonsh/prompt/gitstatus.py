"""Informative git status prompt formatter.

Each part of the status field is extendable and customizable.

For example, if you do not want to lines_added or lines_removed in the final prompt
subclass the status field, and remove these two from the fields attribute ::

    import xonsh.prompt.gitstatus as gs
    gs.GSNumbers.fields = (
        GSStaged,
        GSConflicts,
        GSChanged,
        GSDeleted,
        GSUntracked,
        GSStashed,
    )

"""

import os
import subprocess

from xonsh.prompt.base import PromptField


def _check_output(xsh, *args, **kwargs) -> str:
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


class GSField(PromptField):
    """base class to ease implementing other GS* fields"""

    args = ()
    info_field = None

    def check_output(self, *args: str):
        return _check_output(self.xsh, args).strip()

    def get_value(self):
        return self.check_output(*self.args)


class GSHash(GSField):
    prefix = ":"
    args = ("git", "rev-parse", "--short", "HEAD")


class GSTag(GSField):
    args = ("git", "describe", "--always")


class GSTagOrHash(GSField):
    def get_value(self):
        return self.get(GSTag) or self.get(GSHash)


def _parse_int(val: str, default=0):
    if val.isdigit():
        return int(val)
    return default


class GSDir(GSField):
    args = ("git", "rev-parse", "--git-dir")


class GSStashed(GSField):
    prefix = "⚑"

    def get_value(self):
        gitdir = self.get(GSDir)
        try:
            with open(os.path.join(gitdir, "logs/refs/stash")) as f:
                return sum(1 for _ in f)
        except OSError:
            return 0


class GSOperation(GSField):
    prefix = "{CYAN}"
    separator = "|"

    def get_value(self):
        gitdir = self.get(GSDir)

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
            return self.separator + self.separator.join(operations)


class GSNumstat(GSField):
    def get_value(self):
        changed = self.check_output("git", "diff", "--numstat")

        insert = 0
        delete = 0

        if changed:
            for line in changed.splitlines():
                x = line.split(maxsplit=2)
                if len(x) > 1:
                    insert += _parse_int(x[0])
                    delete += _parse_int(x[1])

        return insert, delete


class GSPorcelain(GSField):
    args = ("git", "status", "--porcelain", "--branch")


class GSInfo(GSField):
    """Return parsed values from ``git status``"""

    def get_value(self):
        status = self.get(GSPorcelain)
        branch = ""
        ahead, behind = 0, 0
        untracked, changed, deleted, conflicts, staged = 0, 0, 0, 0, 0
        for line in status.splitlines():
            if line.startswith("##"):
                line = line[2:].strip()
                if "Initial commit on" in line:
                    branch = line.split()[-1]
                elif "no branch" in line:
                    branch = self.get(GSTagOrHash)
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
            "branch": branch,
            "ahead": ahead,
            "behind": behind,
            "untracked": untracked,
            "changed": changed,
            "deleted": deleted,
            "conflicts": conflicts,
            "staged": staged,
        }


class GSBranch(GSField):
    prefix = "{CYAN}"
    info_field = "branch"


class GSAhead(GSField):
    prefix = "↑·"
    info_field = "ahead"


class GSBehind(GSField):
    prefix = "↓·"
    info_field = "behind"


class GSUntracked(GSField):
    prefix = "…"
    info_field = "untracked"


class GSChanged(GSField):
    prefix = "{BLUE}+"
    info_field = "changed"


class GSDeleted(GSField):
    prefix = "{RED}-"
    info_field = "deleted"


class GSConflicts(GSField):
    prefix = "{RED}×"
    info_field = "conflicts"


class GSStaged(GSField):
    info_field = "staged"
    prefix = "{RED}●"


class GSLinesAdded(GSField):
    prefix = "{BLUE}+"

    def get_value(self):
        return self.get(GSNumstat).value[0]


class GSLinesRemoved(GSField):
    prefix = "{RED}-"

    def get_value(self):
        return self.get(GSNumstat).value[-1]


class GSClean(GSField):
    prefix = "{BOLD_GREEN}"
    symbol = "✓"

    def get_value(self):
        for fld in (
            GSStaged,
            GSConflicts,
            GSChanged,
            GSDeleted,
            GSUntracked,
            GSStashed,
        ):
            changes = self.get(fld)
            if changes:
                return
        return self.symbol


class GSNumbers(GSField):
    fields = (
        GSStaged,
        GSConflicts,
        GSChanged,
        GSDeleted,
        GSUntracked,
        GSStashed,
        GSLinesAdded,
        GSLinesRemoved,
        GSClean,
    )


class GSBranchPart(GSField):
    fields = (GSBranch, GSAhead, GSBehind, GSOperation)


class GSPrompt(GSField):
    """Return str `BRANCH|OPERATOR|numbers`"""

    join = "{RESET}|"
    fields = (GSBranchPart, GSNumbers)
