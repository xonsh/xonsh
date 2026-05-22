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

import os.path

from xonsh.aliases import source_foreign_fn


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
