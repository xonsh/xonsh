#!/usr/bin/env python3
"""Manage the xonsh nightly-build GitHub release notes.

Subcommands:
  header --sha SHA --date DATE
      Create nightly-build release (if missing) or update its first-line
      header ``xonsh <SHA> (<DATE>)``, preserving everything below.

  line --file NAME --sha SHA
      Add or update a ``* <NAME> - xonsh <SHA>`` line in the release body.
      If the line for <NAME> already exists, its SHA is replaced; otherwise
      the line is appended.

Because 6 nightly jobs update the release body in parallel and the GitHub
API has no ETag / compare-and-swap, every write is followed by a re-read
and retried with jitter if another job overwrote our change. Eventually
consistent: ``MAX_ATTEMPTS`` bounds the retry loop.

Requires the ``gh`` CLI with ``GITHUB_TOKEN`` in the environment.
"""

from __future__ import annotations

import argparse
import random
import re
import subprocess
import sys
import time

MAX_ATTEMPTS = 12


def get_body() -> str | None:
    r = subprocess.run(
        ["gh", "release", "view", "nightly-build", "--json", "body", "--jq", ".body"],
        capture_output=True,
        text=True,
    )
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def gh_edit(notes: str, with_title: bool = False) -> None:
    args = ["gh", "release", "edit", "nightly-build", "--notes", notes]
    if with_title:
        args += ["--title", "Nightly build", "--prerelease"]
    subprocess.run(args, check=True)


def gh_create(notes: str) -> None:
    subprocess.run(
        [
            "gh", "release", "create", "nightly-build",
            "--title", "Nightly build",
            "--notes", notes,
            "--prerelease",
        ],
        check=True,
    )


def commit(transform, verify, with_title: bool = False) -> None:
    """Apply ``transform(body) -> new_body`` and retry until ``verify`` passes.

    Concurrent writers from other jobs may overwrite our change between the
    edit and the re-read; in that case we recompute against the new body.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        body = get_body() or ""
        new_body = transform(body)
        gh_edit(new_body, with_title=with_title)
        # Longer settle window so any in-flight concurrent writer can finish
        # and, if they clobbered us, our re-verify will catch it.
        time.sleep(random.uniform(2.0, 6.0))
        if verify(get_body() or ""):
            return
        print(
            f"[{attempt}/{MAX_ATTEMPTS}] change overwritten by a concurrent "
            f"job, retrying",
            file=sys.stderr,
        )
    raise SystemExit(f"failed to commit change after {MAX_ATTEMPTS} attempts")


def cmd_header(args: argparse.Namespace) -> None:
    header = f"xonsh {args.sha} ({args.date})"

    # First time — release doesn't exist yet.
    if get_body() is None:
        gh_create(header)
        return

    def transform(b: str) -> str:
        lines = b.split("\n") if b else []
        if lines and lines[0].startswith("xonsh "):
            lines[0] = header
        else:
            lines.insert(0, header)
        return "\n".join(lines)

    def verify(b: str) -> bool:
        first = b.split("\n", 1)[0] if b else ""
        return first == header

    commit(transform, verify, with_title=True)


def cmd_line(args: argparse.Namespace) -> None:
    line = f"* `{args.file}` - xonsh {args.sha}"
    pattern = re.compile(rf"^\* `?{re.escape(args.file)}`? - xonsh .*$", re.M)
    exact = re.compile(rf"^{re.escape(line)}$", re.M)

    def transform(b: str) -> str:
        if pattern.search(b):
            return pattern.sub(line, b)
        return f"{b}\n{line}" if b else line

    commit(transform, lambda b: bool(exact.search(b)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_hdr = sub.add_parser("header", help="create release or update header")
    p_hdr.add_argument("--sha", required=True)
    p_hdr.add_argument("--date", required=True)
    p_hdr.set_defaults(func=cmd_header)

    p_line = sub.add_parser("line", help="add or update per-file line")
    p_line.add_argument("--file", required=True)
    p_line.add_argument("--sha", required=True)
    p_line.set_defaults(func=cmd_line)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
