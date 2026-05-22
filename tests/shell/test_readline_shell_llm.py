"""LLM-generated tests for the readline shell."""

import sys

import pytest

from xonsh.pytest.tools import skip_if_on_windows
from xonsh.shells.readline_shell import _ensure_newline


class _FakeStdin:
    """Stand-in for sys.stdin with a fileno — pytest's capture replaces
    the real stdin with a pseudofile that raises on fileno()."""

    def fileno(self):
        return 0


@skip_if_on_windows
@pytest.mark.parametrize("var", ["SSH_TTY", "SSH_CONNECTION"])
def test_ensure_newline_skipped_inside_ssh(monkeypatch, capsys, var):
    """No DSR (``\\x1b[6n``) query when running inside an SSH session.

    The terminal's reply to DSR travels back through stdin and is
    observed by the local ssh client's tilde-escape filter; a reply
    arriving between the user's Enter and the following ``~`` resets
    ``last_was_cr`` to 0, silently breaking ssh ``~.`` etc. (#5686).
    """
    monkeypatch.setattr(sys, "stdin", _FakeStdin())
    monkeypatch.setattr("os.isatty", lambda fd: True)
    for v in ("SSH_TTY", "SSH_CONNECTION"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv(var, "/dev/pts/0")

    _ensure_newline()

    # No DSR query and no newline written to stdout — the function
    # short-circuited before reaching the ``sys.stdout.write("\\033[6n")``.
    assert capsys.readouterr().out == ""
