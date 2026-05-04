"""Token-stream based formatter for xonsh source code.

The formatter walks the raw token stream produced by
:mod:`xonsh.parsers.tokenize` (which preserves comments, blank lines and
all xonsh-specific tokens such as ``$(``, ``!(``, ``${``, ``@$``, IO
redirects and globs) and re-emits the source with normalized whitespace
and indentation.

The public API is intentionally small:

- :func:`format_source` — format a string of xonsh source.
- :class:`FormatError` — raised on unrecoverable tokenizer errors.

The CLI entry point used by ``xonsh format ...`` lives in
:mod:`xonsh.formatter.cli`.
"""

from xonsh.formatter.core import DEFAULT_INDENT, FormatError, format_source

__all__ = ["DEFAULT_INDENT", "FormatError", "format_source"]
