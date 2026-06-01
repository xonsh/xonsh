"""Command-line interface for ``xonsh check`` and the ``-n`` flag.

The dispatcher in :mod:`xonsh.main` peeks at ``sys.argv`` and, if the first
non-option argument is ``check``, hands the rest off to :func:`main` here. As
with ``xonsh format`` we deliberately do *not* go through xonsh's own argparse:
syntax checking needs no shell session, xontribs or rc files, and avoiding that
machinery makes startup fast and side-effect free.

The thin top-level ``xonsh -n`` / ``--no-execute`` flag is wired into
:func:`xonsh.main.premain` and delegates to :func:`check_no_execute` here, so
both spellings share one engine (:func:`check_source`).

Behaviour
---------
* ``xonsh check FILE...`` checks each path and prints ``FILE: OK`` per file
  (suppressed with ``-q``); ``-`` reads from stdin.
* ``xonsh -n`` checks the ``-c`` command, the script file, or piped stdin —
  whatever a normal invocation would have run — and stays silent on success,
  matching ``bash -n``.

Exit codes
----------
* ``0`` — every input parsed and compiled successfully;
* ``1`` — at least one input had a syntax/compile error;
* ``123`` — at least one path could not be read (missing file, a directory,
  unreadable, …).
"""

from __future__ import annotations

import argparse
import os
import sys

_PROG = "xonsh check"
EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_ERROR = 123

_EXECER = None


def _get_execer():
    """Return a process-wide :class:`~xonsh.execer.Execer`, with a session.

    Building an ``Execer`` constructs the (relatively expensive) PLY parser
    tables, so we build one lazily and reuse it across every file in a single
    ``xonsh check`` run. ``Execer.compile`` is a synchronous, fully-resetting
    call and the CLI is single-threaded, so sharing the instance is safe.

    Parsing is not fully self-contained: the context-aware phase
    (:mod:`xonsh.parsers.ast`) and the subprocess-recovery helpers
    (:mod:`xonsh.tools`) read ``XSH.execer``/``XSH.env``/``XSH.aliases``/
    ``XSH.commands_cache`` off the *global* session. So we bring up a minimal
    session, exactly as :func:`xonsh.main.start_services` does right before it
    compiles — but WITHOUT starting a shell, loading rc files or xontribs, and
    of course without ever running the checked source.
    """
    global _EXECER
    if _EXECER is None:
        from xonsh.built_ins import XSH
        from xonsh.execer import Execer

        if XSH.execer is not None:
            # A session is already active (under pytest, or an embedding
            # application) — reuse its execer so the global-session lookups in
            # the parser agree with what we compile.
            _EXECER = XSH.execer
        else:
            execer = Execer(filename="<check>")
            XSH.load(ctx={}, execer=execer)
            _EXECER = execer
    return _EXECER


def check_source(src: str, filename: str = "<check>", mode: str = "exec", execer=None):
    """Parse and compile xonsh *src* to validate its syntax, without running it.

    Raises ``SyntaxError`` (or a subclass such as ``IndentationError`` /
    ``TabError``) if *src* does not parse or compile. Returns ``None`` on
    success. No code from *src* is executed and no rc files, xontribs or
    interactive shell are loaded. The compile runs against an empty user
    context (builtins only); a minimal xonsh session may be brought up on
    first use for the parser's context-aware phase (see :func:`_get_execer`).
    """
    if execer is None:
        execer = _get_execer()
    if not src.endswith("\n"):
        src += "\n"
    # glbs/locs are passed explicitly (and empty) so the compiler does not
    # inspect the caller's frame and no user names leak into subprocess-vs-
    # Python disambiguation. Comment-only / empty input compiles to ``pass``.
    execer.compile(src, glbs={}, locs={}, mode=mode, filename=filename)


def _diagnostic_lines(name: str, exc: Exception) -> list[str]:
    """Render *exc* as compact, greppable ``path:line:col: message`` lines."""
    if isinstance(exc, SyntaxError):
        loc = name
        if exc.lineno:
            loc += f":{exc.lineno}"
            if exc.offset:
                loc += f":{exc.offset}"
        lines = [f"{loc}: {exc.msg or 'invalid syntax'}"]
        text = (exc.text or "").rstrip("\n")
        if text:
            lines.append("    " + text)
            if exc.offset and exc.offset >= 1:
                lines.append("    " + " " * (exc.offset - 1) + "^")
        return lines
    # e.g. ValueError("source code string cannot contain null bytes")
    return [f"{name}: error: {exc}"]


def _check_text(
    src: str, name: str, execer, mode: str = "exec", quiet: bool = False
) -> bool:
    """Check one string. Return ``True`` if valid, ``False`` on syntax error.

    On success an ``OK`` line is printed unless *quiet*; on failure the
    diagnostic is always printed to stderr.
    """
    try:
        check_source(src, filename=name, mode=mode, execer=execer)
    except (SyntaxError, ValueError) as exc:
        for line in _diagnostic_lines(name, exc):
            print(line, file=sys.stderr)
        return False
    if not quiet:
        print(f"{name}: OK", file=sys.stderr)
    return True


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_PROG,
        description="Check xonsh source files for syntax errors without "
        "running them.",
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="One or more files to check. Use '-' to read from stdin.",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only report files with errors; suppress per-file 'OK' output.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``xonsh check FILE...``."""
    args = build_parser().parse_args(argv)
    execer = _get_execer()

    had_syntax_error = False
    had_read_error = False
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
            had_read_error = True
            continue
        if not _check_text(src, name, execer, mode="exec", quiet=args.quiet):
            had_syntax_error = True

    # Operational failures take precedence over syntax errors, mirroring the
    # exit-code ordering of the sibling ``xonsh format`` subcommand.
    if had_read_error:
        return EXIT_ERROR
    if had_syntax_error:
        return EXIT_SYNTAX
    return EXIT_OK


def check_no_execute(args) -> int:
    """Implements ``xonsh -n`` / ``--no-execute``.

    Checks whatever the invocation would otherwise have run — the ``-c``
    command, the script file, or piped stdin — using the same input precedence
    as :func:`xonsh.main.premain`, and stays silent on success.
    """
    execer = _get_execer()

    if args.command is not None:
        # ``-c`` runs in "single" mode at runtime; match it so the check
        # agrees exactly with what ``xonsh -c`` would compile.
        ok = _check_text(args.command, "<string>", execer, mode="single", quiet=True)
        return EXIT_OK if ok else EXIT_SYNTAX

    if args.file is not None:
        path = os.path.abspath(os.path.expanduser(args.file))
        if os.path.isdir(path):
            print(f"xonsh: {args.file}: Is a directory.", file=sys.stderr)
            return EXIT_ERROR
        try:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
        except OSError as exc:
            print(f"xonsh: {args.file}: {exc.strerror or exc}", file=sys.stderr)
            return EXIT_ERROR
        ok = _check_text(src, args.file, execer, mode="exec", quiet=True)
        return EXIT_OK if ok else EXIT_SYNTAX

    if not sys.stdin.isatty():
        src = sys.stdin.read()
        ok = _check_text(src, "<stdin>", execer, mode="exec", quiet=True)
        return EXIT_OK if ok else EXIT_SYNTAX

    print(
        "xonsh: -n/--no-execute: nothing to check "
        "(give -c CMD, a script file, or piped input)",
        file=sys.stderr,
    )
    return EXIT_ERROR
