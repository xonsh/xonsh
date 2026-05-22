"""LLM-generated tests for the ``source-foreign`` family (issue #4977).

Covers the user-facing error path of :func:`xonsh.aliases.source_foreign_fn`
when the foreign shell subprocess fails. The legacy message was

    xonsh: error: Source failed: 'source /path\\n'
    xonsh: error: Possible reasons: File not found or syntax error

— both lines were misleading: the literal ``\\n`` came from ``repr()`` of
the assembled ``prevcmd``, and the "file not found or syntax error"
diagnosis was wrong for the most common real-world cause (a sourced
``.zshrc``/``.bashrc`` that early-exits with ``return 1``).
"""

import functools
import os.path

import pytest

from xonsh.aliases import make_default_aliases, source_foreign_fn


def test_source_foreign_failure_message_is_helpful(monkeypatch, xession):
    """The error printed when sourcing fails must name the file
    (without a literal ``\\n`` from ``repr()``) and mention non-zero
    exit as a plausible cause — the legacy "File not found or syntax
    error" was wrong whenever a real ``.zshrc`` returned non-zero from
    an early-exit guard.
    """

    def fake_foreign_shell_data(*args, **kwargs):
        return None, None

    fake_foreign_shell_data.cache_clear = lambda: None
    monkeypatch.setattr(
        "xonsh.aliases.foreign_shell_data", fake_foreign_shell_data, raising=False
    )
    monkeypatch.setattr(os.path, "isfile", lambda _: True)

    out, err, rc = source_foreign_fn("bash", ["/etc/profile"], sourcer="source")

    assert rc == 1
    assert out is None
    # The file path appears verbatim — no repr() escaping.
    assert "/etc/profile" in err
    assert "\\n" not in err
    # New wording mentions non-zero exit as a plausible cause and points
    # at ``--show-output`` for richer diagnostics.
    assert "returned non-zero" in err
    assert "--show-output" in err
    # Legacy misleading wording is gone.
    assert "File not found or syntax error" not in err


def test_source_sh_alias_registered(xession):
    """Issue #5894: ``source-sh`` is registered alongside ``source-bash``
    and ``source-zsh``, with a POSIX-safe ``.`` sourcer default (since
    ``/bin/sh`` on Debian/Ubuntu/Alpine is dash, which rejects
    ``source``)."""
    aliases = make_default_aliases()
    assert "source-sh" in aliases

    # Unwrap the ``functools.partial`` to confirm the defaults bound at
    # registration time. The shape mirrors the bash/zsh entries.
    bound = aliases["source-sh"].kwargs["func"]
    assert isinstance(bound, functools.partial)
    assert bound.args == ("sh",)
    assert bound.keywords == {"sourcer": "."}


# ---------------------------------------------------------------------------
# Issue #5895: ``source-foreign <shell> <file>`` used to require
# ``--sourcer`` even when the shell was one of the well-known ones
# (bash/zsh/sh/cmd) that already have a default in DEFAULT_SOURCERS.
# The fix falls back to that default; only truly unknown shells still
# error out, and with a clearer message that mentions ``--sourcer``.
# ---------------------------------------------------------------------------


def _spy_prevcmd(monkeypatch):
    """Replace ``foreign_shell_data`` with a recorder that captures the
    ``prevcmd`` and ``sourcer`` kwargs without running a real subprocess.
    """
    calls = {}

    def fake_foreign_shell_data(*args, **kwargs):
        calls["kwargs"] = kwargs
        return {}, {}

    fake_foreign_shell_data.cache_clear = lambda: None
    monkeypatch.setattr(
        "xonsh.aliases.foreign_shell_data", fake_foreign_shell_data, raising=False
    )
    return calls


@pytest.mark.parametrize(
    "shell, expected_sourcer",
    [
        ("bash", "source"),
        ("/bin/bash", "source"),
        ("zsh", "source"),
        ("/bin/zsh", "source"),
        ("sh", "."),
        ("/bin/sh", "."),
    ],
)
def test_source_foreign_resolves_default_sourcer(
    monkeypatch, xession, shell, expected_sourcer
):
    """Without ``--sourcer``, source-foreign falls back to the known
    default for the shell (``source`` for bash/zsh, POSIX ``.`` for sh).
    """
    calls = _spy_prevcmd(monkeypatch)
    monkeypatch.setattr(os.path, "isfile", lambda _: True)

    # On success ``source_foreign_fn`` falls through with no return value
    # — what matters is that we *got* to foreign_shell_data (no early
    # ``--sourcer`` bail-out) and that ``prevcmd`` was built with the
    # right per-shell default.
    result = source_foreign_fn(shell, ["/etc/profile"])
    assert result is None
    prevcmd = calls["kwargs"]["prevcmd"]
    assert prevcmd == f"{expected_sourcer} /etc/profile"


def test_source_foreign_unknown_shell_without_sourcer_errors_clearly(
    monkeypatch, xession
):
    """A shell that isn't in CANON_SHELL_NAMES and no ``--sourcer`` →
    we cannot guess how to source the file, so error out with a
    message naming the shell and pointing at the ``--sourcer`` flag."""
    monkeypatch.setattr(os.path, "isfile", lambda _: True)

    out, err, rc = source_foreign_fn("/opt/fish/bin/fish", ["/etc/profile"])

    assert rc == 1
    assert out is None
    assert "/opt/fish/bin/fish" in err
    assert "--sourcer" in err
    # Legacy unhelpful wording is gone.
    assert "is not mentioned" not in err


def test_source_foreign_explicit_sourcer_still_wins(monkeypatch, xession):
    """A user-supplied ``--sourcer`` overrides the default even when the
    shell would have provided one — needed for things like ``--sourcer .``
    on bash to force POSIX-style sourcing."""
    calls = _spy_prevcmd(monkeypatch)
    monkeypatch.setattr(os.path, "isfile", lambda _: True)

    source_foreign_fn("bash", ["/etc/profile"], sourcer=".")

    assert calls["kwargs"]["prevcmd"] == ". /etc/profile"
