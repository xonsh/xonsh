"""LLM-authored tests for :mod:`xonsh.main`.

Module-mirroring home for generated tests of ``xonsh/main.py``. Each test
documents the specific behavior it pins down in its own docstring.
"""

import builtins
import os
import subprocess as sp
import sys

import pytest

import xonsh.main
from xonsh.platform import HAS_PYGMENTS, ON_WINDOWS


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


# A launcher that is a POSIX-shell header plus a binary payload, the shape of
# mill's ``*-assembly`` jar-in-a-script from gh-5064. The shell part ends with
# ``exit 0`` so the payload is never interpreted by the shell either.
_POLYGLOT = b"#!/bin/sh\necho polyglot-ran\nexit 0\n\x98\x97\x00archive-bytes\n"


def _run_xonsh_script(script, tmp_path):
    """Run ``xonsh <script>`` in a subprocess with isolated config dirs."""
    popen_env = dict(os.environ)
    popen_env.update(
        {
            "XONSH_CONFIG_DIR": str(tmp_path / "config"),
            "XONSH_DATA_DIR": str(tmp_path / "data"),
            "XONSH_CACHE_DIR": str(tmp_path / "cache"),
            "XONSH_HISTORY_BACKEND": "dummy",
            "XONSH_SHOW_TRACEBACK": "0",
        }
    )
    return sp.run(
        [sys.executable, "-m", "xonsh", "--no-rc", str(script)],
        capture_output=True,
        text=True,
        env=popen_env,
        timeout=120,
    )


@pytest.mark.skipif(ON_WINDOWS, reason="needs a POSIX shebang interpreter")
def test_a_script_with_a_binary_payload_runs_through_its_shebang(tmp_path):
    """gh-5064: a polyglot launcher is executed instead of failing to decode.

    xonsh reads a script whole and hands it to the compiler, so the binary
    payload raised ``UnicodeDecodeError`` before the shell part could run. The
    file is a program for the interpreter in its shebang, so xonsh runs it as
    one, exactly as ``./that-file`` would.
    """
    script = tmp_path / "launcher"
    script.write_bytes(_POLYGLOT)
    script.chmod(0o755)

    proc = _run_xonsh_script(script, tmp_path)

    assert "UnicodeDecodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
    assert "polyglot-ran" in proc.stdout


def test_a_non_text_script_says_why_it_cannot_run(tmp_path):
    """The decode failure becomes a diagnosis, never a traceback.

    A non-text script that the operating system cannot execute either (no
    shebang support on this platform, or no execute permission) cannot be run
    as a program, so xonsh explains the situation and exits non-zero.
    """
    script = tmp_path / "launcher"
    script.write_bytes(_POLYGLOT)  # deliberately left non-executable

    proc = _run_xonsh_script(script, tmp_path)

    assert "UnicodeDecodeError" not in proc.stderr
    assert proc.returncode != 0
    assert "contains binary data" in proc.stderr


def test_a_text_script_still_runs_as_xonsh_source(tmp_path):
    """Compiling the script as xonsh source is unchanged for real scripts."""
    script = tmp_path / "plain.xsh"
    script.write_text("print('xonsh-source-ran')\n", encoding="utf-8")

    proc = _run_xonsh_script(script, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "xonsh-source-ran" in proc.stdout
