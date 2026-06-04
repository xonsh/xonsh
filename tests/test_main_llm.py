"""LLM-authored tests for :mod:`xonsh.main`.

Module-mirroring home for generated tests of ``xonsh/main.py``. Each test
documents the specific behavior it pins down in its own docstring.
"""

import builtins

import pytest

import xonsh.main
from xonsh.platform import HAS_PYGMENTS


@pytest.fixture
def restore_underscore():
    """``_pprint_displayhook`` writes the value to ``builtins._``.

    Snapshot and restore it so the displayed value does not leak into other
    tests through the ``_`` builtin.
    """
    sentinel = object()
    prev = getattr(builtins, "_", sentinel)
    yield
    if prev is sentinel:
        if hasattr(builtins, "_"):
            del builtins._
    else:
        builtins._ = prev


class _AnsiRepr:
    """Helper whose repr is colored with raw ANSI escape sequences."""

    def __repr__(self):
        return "\x1b[31mhello\x1b[0m"


def test_displayhook_passes_ansi_repr_through_verbatim(
    xession, capsys, mocker, restore_underscore
):
    """An ANSI-colored repr is shown verbatim, not re-highlighted (gh-6503).

    When ``__repr__`` already emits terminal escapes, re-lexing the string as
    xonsh source splits the escapes into separate tokens and prompt_toolkit then
    sanitizes the raw ESC bytes, so the color never renders. The displayhook must
    instead pass it straight through, like CPython's default ``sys.displayhook``.
    """
    print_color = mocker.patch("xonsh.main.print_color")
    xession.env["COLOR_RESULTS"] = True
    xession.env["PRETTY_PRINT_RESULTS"] = True

    xonsh.main._pprint_displayhook(_AnsiRepr())

    out, _ = capsys.readouterr()
    # The escape sequence survives byte-for-byte (matching print(repr(foo))) ...
    assert out == "\x1b[31mhello\x1b[0m\n"
    # ... and the pygments + prompt_toolkit highlighting path was skipped.
    print_color.assert_not_called()


def test_displayhook_passes_ansi_repr_with_pretty_print_off(
    xession, capsys, mocker, restore_underscore
):
    """Passthrough also applies when PRETTY_PRINT_RESULTS falls back to repr()."""
    print_color = mocker.patch("xonsh.main.print_color")
    xession.env["COLOR_RESULTS"] = True
    xession.env["PRETTY_PRINT_RESULTS"] = False

    xonsh.main._pprint_displayhook(_AnsiRepr())

    out, _ = capsys.readouterr()
    assert out == "\x1b[31mhello\x1b[0m\n"
    print_color.assert_not_called()


@pytest.mark.skipif(not HAS_PYGMENTS, reason="pygments not installed")
def test_displayhook_highlights_plain_repr(xession, capsys, mocker, restore_underscore):
    """A normal repr (no embedded escapes) still goes through highlighting."""
    print_color = mocker.patch("xonsh.main.print_color")
    xession.env["COLOR_RESULTS"] = True
    xession.env["PRETTY_PRINT_RESULTS"] = True

    xonsh.main._pprint_displayhook([1, 2, 3])

    # Highlighting path taken: print_color receives the lexed tokens ...
    print_color.assert_called_once()
    tokens = print_color.call_args.args[0]
    assert "".join(text for _, text in tokens).rstrip("\n") == "[1, 2, 3]"
    # ... and nothing was emitted through the raw print branch.
    out, _ = capsys.readouterr()
    assert out == ""
