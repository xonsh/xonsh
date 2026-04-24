"""Tests for :func:`xonsh.completers.bash_completion._bash_quote_paths`.

Covers two behaviours, both mirroring the corresponding logic in the
path completer (``xonsh.completers.path._quote_paths``):

1. **Per-path quoting** — only paths that actually contain shell-special
   characters get quoted. A plain ``file`` sibling to ``fi$le`` stays
   unquoted; without this, readline-era "quote all or none" logic made
   every completion look like ``'file'`` in the prompt-toolkit menu.

2. **Trailing space outside quotes** — a file completion inside quotes
   must end with ``'file' `` (space *after* the closing quote) so
   ``ls 'f<Tab>`` advances to the next argument, matching
   ``ls f<Tab>``. Directories keep the trailing separator (no space)
   and ``--opt=`` args stay glued to the value the user will type next.
"""

import os
import tempfile

from xonsh.completers.bash_completion import _bash_quote_paths


def test_per_path_quoting_leaves_plain_file_unquoted():
    """A plain ``file`` must not be quoted just because a sibling needs
    raw-string quoting — ptk's menu renders mixed entries fine.
    """
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "file"), "w").close()
        open(os.path.join(td, "fi$le"), "w").close()
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            out, _ = _bash_quote_paths({"file", "fi$le"}, "", "")
        finally:
            os.chdir(old_cwd)
    assert "file " in out, f"plain 'file' should be unquoted, got: {out}"
    assert any(c.startswith("'fi$le'") or c.startswith("r'fi$le'") for c in out), (
        f"'fi$le' should be quoted, got: {out}"
    )


def test_quoted_file_appends_trailing_space_outside_quotes():
    """File completion inside quotes ends with ``'file' `` — the space
    sits *after* the closing quote so the next arg starts cleanly.
    """
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "fi$le"), "w").close()
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            out, _ = _bash_quote_paths({"fi$le"}, "", "")
        finally:
            os.chdir(old_cwd)
    assert out == {"'fi$le' "}, f"expected trailing space after quote: {out}"


def test_quoted_dir_keeps_sep_no_trailing_space():
    """Directory completion keeps the trailing path separator and does
    not add a space — a second Tab should drill in, not commit the arg.
    """
    with tempfile.TemporaryDirectory() as td:
        os.mkdir(os.path.join(td, "di$r"))
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            out, _ = _bash_quote_paths({"di$r"}, "", "")
        finally:
            os.chdir(old_cwd)
    sep = os.sep
    assert out == {f"'di$r{sep}'"}, f"expected dir ending with sep, no space: {out}"


def test_equals_terminated_arg_gets_no_trailing_space():
    """``--opt=`` style args must stay glued to whatever value follows.
    This was historically guarded by ``not s.endswith("=")`` in the
    unquoted branch; the quoted branch needs the same guard.
    """
    # No quoting needed — just an equals-terminated plain arg.
    out, _ = _bash_quote_paths({"--opt="}, "", "")
    assert out == {"--opt="}, f"no space/quote for '--opt=': {out}"


def test_user_supplied_quotes_preserved_across_all_paths():
    """When the user has already opened a quote (``ls 'fi<Tab>``), every
    completion inherits it — per-path logic only decides whether to
    *add* quotes, not to strip them.
    """
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "file"), "w").close()
        open(os.path.join(td, "fi$le"), "w").close()
        old_cwd = os.getcwd()
        os.chdir(td)
        try:
            out, _ = _bash_quote_paths({"file", "fi$le"}, "'", "'")
        finally:
            os.chdir(old_cwd)
    # Both entries must be wrapped in the user's single quotes.
    assert "'file' " in out, f"user quote preserved for plain file: {out}"
    assert any("'fi$le'" in c and "\\" not in c[:-1] for c in out), (
        f"user quote preserved for fi$le: {out}"
    )
