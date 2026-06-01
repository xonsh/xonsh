"""Syntax checking ("no-execute" validation) for xonsh source code.

This package parses and compiles xonsh source all the way down to a Python
code object, but never executes it.  It is the xonsh analogue of ``bash -n``,
``fish --no-execute`` or ``nu --no-execute``: a fast, side-effect free way to
answer the single question *"does this parse and compile?"* without running a
shell session, rc files or xontribs.

It is **not** a linter — it reports syntax/compile errors only, not style or
semantic diagnostics.

The public API is intentionally small:

- :func:`check_source` — parse + compile a string of xonsh source, raising
  ``SyntaxError`` on failure.
- :class:`CheckError` is not needed; failures surface as ``SyntaxError``.

The CLI entry point used by ``xonsh check ...`` (and the ``xonsh -n`` /
``--no-execute`` flag) lives in :mod:`xonsh.checker.cli`.
"""

from xonsh.checker.cli import check_source

__all__ = ["check_source"]
