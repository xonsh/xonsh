"""Command-line interface for ``xonsh format``.

The dispatcher in :mod:`xonsh.main` peeks at ``sys.argv`` and, if the
first non-option argument is ``format``, hands the rest off to
:func:`main` here. We deliberately do *not* go through xonsh's own
argparse — the format subcommand has no need for a shell session,
xontribs, or rc files, and avoiding that machinery makes ``xonsh
format`` startup fast and side-effect free.

Behaviour mirrors common formatters (e.g. Black):

* by default each path is rewritten in place;
* ``--check`` reports which files would change and exits non-zero;
* ``--diff`` writes a unified diff to stdout instead of touching files;
* ``-`` reads from stdin and writes to stdout.

Exit codes
----------
* ``0`` — nothing needed reformatting (or every file was rewritten
  successfully when not in ``--check`` / ``--diff`` mode);
* ``1`` — at least one file would be (or was) changed in
  ``--check`` / ``--diff`` mode;
* ``123`` — at least one file failed to tokenize or could not be read /
  written.
"""

from __future__ import annotations

import argparse
import difflib
import sys

from xonsh.formatter.core import FormatError, format_source

_PROG = "xonsh format"
EXIT_OK = 0
EXIT_CHANGED = 1
EXIT_ERROR = 123


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_PROG,
        description="Format xonsh source files in place.",
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="One or more files to format. Use '-' to read from stdin "
        "and write to stdout.",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Don't write the files back. Exit with code 1 if any file "
        "would be changed.",
    )
    p.add_argument(
        "--diff",
        action="store_true",
        help="Don't write the files back. Print a unified diff for "
        "each file that would change. Exit code matches --check.",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress per-file status messages on stderr.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    changed = 0
    errors = 0
    for path in args.files:
        try:
            rc = _process_one(path, args)
        except FormatError as exc:
            print(f"{path}: error: {exc}", file=sys.stderr)
            errors += 1
            continue
        except OSError as exc:
            print(f"{path}: error: {exc}", file=sys.stderr)
            errors += 1
            continue
        if rc:
            changed += 1

    if errors:
        return EXIT_ERROR
    if (args.check or args.diff) and changed:
        return EXIT_CHANGED
    return EXIT_OK


def _process_one(path: str, args: argparse.Namespace) -> bool:
    """Format one file; return True if it changed (or would have)."""
    if path == "-":
        original = sys.stdin.read()
        formatted = format_source(original)
        if args.check:
            if original != formatted and not args.quiet:
                print("stdin: would reformat", file=sys.stderr)
            return original != formatted
        if args.diff:
            _write_diff("stdin", original, formatted)
            return original != formatted
        sys.stdout.write(formatted)
        return original != formatted

    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    formatted = format_source(original)
    if original == formatted:
        if not args.quiet and not (args.check or args.diff):
            print(f"{path}: unchanged", file=sys.stderr)
        return False

    if args.check:
        if not args.quiet:
            print(f"{path}: would reformat", file=sys.stderr)
        return True
    if args.diff:
        _write_diff(path, original, formatted)
        return True

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(formatted)
    if not args.quiet:
        print(f"{path}: reformatted", file=sys.stderr)
    return True


def _write_diff(name: str, original: str, formatted: str) -> None:
    sys.stdout.writelines(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            formatted.splitlines(keepends=True),
            fromfile=name,
            tofile=f"{name} (formatted)",
        )
    )
