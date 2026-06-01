"""Command-line interface for ``xonsh lint``.

The dispatcher in :mod:`xonsh.main` peeks at ``sys.argv`` and, if the first
non-option argument is ``lint``, hands the rest off to :func:`main` here. As
with ``xonsh check`` / ``xonsh format`` we bypass xonsh's own argparse: linting
needs no shell session, xontribs or rc files.

``xonsh lint`` is the *correctness* sibling of the *style* tool ``xonsh format``
and the *syntax* tool ``xonsh check``. It reuses the checker's parser/session
(:func:`xonsh.checker.cli._get_execer`) to obtain the transformed xonsh AST,
then runs the rules in :mod:`xonsh.linter.rules` over it.

Exit codes
----------
* ``0`` — every file parsed and produced no findings;
* ``1`` — at least one file had a lint finding;
* ``123`` — at least one path could not be read or parsed (syntax error).
"""

from __future__ import annotations

import argparse
import builtins
import sys

from xonsh.linter.rules import ALL_RULES, Finding

_PROG = "xonsh lint"
EXIT_OK = 0
EXIT_LINT = 1
EXIT_ERROR = 123


def lint_source(
    src: str, filename: str = "<lint>", execer=None, ignore=()
) -> list[Finding]:
    """Parse *src* and return the lint findings, sorted by position.

    Raises ``SyntaxError`` (propagated from the parser) if *src* does not parse;
    callers should handle that the same way ``xonsh check`` does. No code is
    executed. Comment-only / empty input yields ``[]``.
    """
    from xonsh.checker.cli import _get_execer

    if execer is None:
        execer = _get_execer()
    if not src.endswith("\n"):
        src += "\n"
    # Mirror Execer.compile's parse step (empty user context, builtins only) but
    # keep the transformed AST instead of compiling it.
    tree = execer.parse(
        src,
        set(dir(builtins)),
        mode="exec",
        filename=filename,
        transform=True,
        user_names=set(),
    )
    if tree is None:
        return []
    findings: list[Finding] = []
    for rule in ALL_RULES:
        findings.extend(rule(tree))
    if ignore:
        findings = [f for f in findings if f.code not in ignore]
    findings.sort(key=lambda f: (f.line, f.col, f.code))
    return findings


def _lint_one(src: str, name: str, execer, quiet: bool, ignore) -> str:
    """Lint one source string. Return 'ok', 'lint', or 'error'."""
    try:
        findings = lint_source(src, filename=name, execer=execer, ignore=ignore)
    except (SyntaxError, ValueError) as exc:
        from xonsh.checker.cli import _diagnostic_lines

        for line in _diagnostic_lines(name, exc):
            print(line, file=sys.stderr)
        return "error"
    if findings:
        for f in findings:
            print(f"{name}:{f.line}:{f.col}: {f.code} {f.message}", file=sys.stderr)
        return "lint"
    if not quiet:
        print(f"{name}: clean", file=sys.stderr)
    return "ok"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_PROG,
        description="Lint xonsh source files for likely mistakes "
        "(env-var typos, bad env-var values, deprecated vars, unused imports).",
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="One or more files to lint. Use '-' to read from stdin.",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only report files with findings; suppress per-file 'clean' output.",
    )
    p.add_argument(
        "--ignore",
        metavar="CODES",
        default="",
        help="Comma-separated rule codes to silence, e.g. --ignore XSH001,XSH101.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``xonsh lint FILE...``."""
    args = build_parser().parse_args(argv)
    ignore = {c.strip().upper() for c in args.ignore.split(",") if c.strip()}

    from xonsh.checker.cli import _get_execer

    execer = _get_execer()

    had_lint = False
    had_error = False
    for path in args.files:
        try:
            if path == "-":
                src, name = sys.stdin.read(), "<stdin>"
            else:
                with open(path, encoding="utf-8") as fh:
                    src = fh.read()
                name = path
        except OSError as exc:
            print(f"{path}: error: {exc.strerror or exc}", file=sys.stderr)
            had_error = True
            continue
        result = _lint_one(src, name, execer, args.quiet, ignore)
        if result == "lint":
            had_lint = True
        elif result == "error":
            had_error = True

    # Unprocessable files (read/parse failures) take precedence, mirroring the
    # exit-code ordering of the sibling ``xonsh check`` subcommand.
    if had_error:
        return EXIT_ERROR
    if had_lint:
        return EXIT_LINT
    return EXIT_OK
