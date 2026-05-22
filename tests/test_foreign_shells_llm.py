"""LLM-generated tests for foreign shell aliases (issue #5043 and friends)."""

import os
import shutil
import subprocess
import tempfile
import warnings

import pytest

from xonsh.pytest.tools import skip_if_on_windows


@skip_if_on_windows
@pytest.mark.skipif(not shutil.which("bash"), reason="bash is not available")
def test_foreign_function_alias_streams_to_caller_stdout(xession):
    """Issue #5043: in streaming mode the foreign shell must write to the
    ``stdout`` argument supplied by the caller (e.g. xonsh's ``$()`` pipe),
    not inherit xonsh's own terminal fd."""
    from xonsh.foreign_shells import ForeignShellFunctionAlias

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as bashrc:
        bashrc.write("function printstuff() { echo printing stuff; }\n")
        bashrc_name = bashrc.name
    try:
        alias = ForeignShellFunctionAlias(
            funcname="printstuff",
            shell="bash",
            sourcer="source",
            files=(bashrc_name,),
        )
        with tempfile.TemporaryFile("w+") as out_file:
            alias([], stdout=out_file, stderr=subprocess.DEVNULL)
            out_file.seek(0)
            captured = out_file.read()
        assert "printing stuff" in captured
    finally:
        os.unlink(bashrc_name)


def test_foreign_shell_nostream_flag_is_deprecated():
    """``--xonsh-nostream`` is a legacy opt-out from the streaming mode.
    Streaming now captures correctly via $(...) / !(...), so the flag is
    redundant and should warn on use."""
    from xonsh.foreign_shells import ForeignShellBaseAlias

    with pytest.warns(DeprecationWarning, match="xonsh-nostream"):
        args, streaming = ForeignShellBaseAlias._is_streaming(
            ["foo", "--xonsh-nostream", "bar"]
        )
    assert streaming is False
    assert args == ["foo", "bar"]


def test_foreign_shell_streaming_default_does_not_warn():
    """No ``--xonsh-nostream`` → no warning, streaming stays the default."""
    from xonsh.foreign_shells import ForeignShellBaseAlias

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning would raise
        args, streaming = ForeignShellBaseAlias._is_streaming(["foo", "bar"])
    assert streaming is True
    assert args == ["foo", "bar"]


def test_emit_foreign_script_output_strips_marker(capsys):
    """The helper must drop everything from the first xonsh marker onward
    when forwarding the script's stdout."""
    from xonsh.foreign_shells import _emit_foreign_script_output

    captured_stdout = (
        "user-line-1\nuser-line-2\n"
        "__XONSH_ENV_BEG__\nFOO=bar\n__XONSH_ENV_END__\n"
        "__XONSH_ALIAS_BEG__\n__XONSH_ALIAS_END__\n"
        "__XONSH_FUNCS_BEG__\n__XONSH_FUNCS_END__\n"
    )
    _emit_foreign_script_output(captured_stdout, "warning-on-stderr\n")

    out = capsys.readouterr()
    assert out.out == "user-line-1\nuser-line-2\n"
    assert "__XONSH_ENV_BEG__" not in out.out
    assert out.err == "warning-on-stderr\n"


def test_emit_foreign_script_output_handles_empty_prefix(capsys):
    """No script output (marker is at position 0) → nothing on stdout."""
    from xonsh.foreign_shells import _emit_foreign_script_output

    _emit_foreign_script_output("__XONSH_ENV_BEG__\nFOO=bar\n", "")
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_emit_foreign_script_output_no_marker_passthrough(capsys):
    """If the marker is missing (e.g. shell crashed), the entire captured
    stdout is the script's — forward it whole instead of swallowing it."""
    from xonsh.foreign_shells import _emit_foreign_script_output

    _emit_foreign_script_output("crashed before marker\n", "stderr msg\n")
    out = capsys.readouterr()
    assert out.out == "crashed before marker\n"
    assert out.err == "stderr msg\n"


@skip_if_on_windows
@pytest.mark.skipif(not shutil.which("bash"), reason="bash is not available")
def test_foreign_shell_data_show_output_forwards_script_stdout(capfd, xession):
    """Issue #4070: with ``show_output=True`` the sourced script's own
    ``echo`` lines must appear on the xonsh terminal."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as script:
        script.write(
            "echo banner-stdout\necho banner-stderr 1>&2\nexport VAR_4070=ok\n"
        )
        script_name = script.name
    try:
        # Forward ``$PATH`` so the bash subprocess can resolve itself, ``env``,
        # and friends — Nix sandboxes have no ``/bin/bash`` fallback and the
        # default ``_PATH_DEFPATH`` (``/bin:/usr/bin``) used when ``env`` lacks
        # ``PATH`` doesn't exist there.
        env, aliases = foreign_shell_data(
            shell="bash",
            currenv=(("PATH", os.environ.get("PATH", "")),),
            interactive=False,
            sourcer="source",
            prevcmd=f"source {script_name}\n",
            files=(script_name,),
            show_output=True,
            safe=False,
        )
    finally:
        os.unlink(script_name)
        foreign_shell_data.cache_clear()

    captured = capfd.readouterr()
    assert env is not None
    assert env.get("VAR_4070") == "ok"
    assert "banner-stdout" in captured.out
    # marker output must never leak to the user
    assert "__XONSH_ENV_BEG__" not in captured.out
    assert "banner-stderr" in captured.err


@skip_if_on_windows
@pytest.mark.skipif(not shutil.which("bash"), reason="bash is not available")
def test_foreign_shell_data_default_silently_swallows_script_output(capfd, xession):
    """Without ``show_output`` (the historical default), the script's own
    output is not forwarded — preserves backward compatibility."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as script:
        script.write("echo silent-banner\nexport VAR_4070_SILENT=ok\n")
        script_name = script.name
    try:
        env, _ = foreign_shell_data(
            shell="bash",
            currenv=(("PATH", os.environ.get("PATH", "")),),
            interactive=False,
            sourcer="source",
            prevcmd=f"source {script_name}\n",
            files=(script_name,),
            safe=False,
        )
    finally:
        os.unlink(script_name)
        foreign_shell_data.cache_clear()

    captured = capfd.readouterr()
    assert env is not None
    assert env.get("VAR_4070_SILENT") == "ok"
    assert "silent-banner" not in captured.out
    assert "silent-banner" not in captured.err


# ---------------------------------------------------------------------------
# Issue #4977: ``source-zsh`` (and friends) gives a misleading
# "File not found or syntax error" message whenever the foreign shell
# subprocess exits non-zero — even when the real cause is a script that
# returned non-zero (e.g. an early-exit guard inside ``.zshrc``). The fix
# auto-surfaces the shell's stderr on every failure, regardless of
# ``--show-output``, so users see why the source actually failed.
# ---------------------------------------------------------------------------


@skip_if_on_windows
@pytest.mark.skipif(not shutil.which("bash"), reason="bash is not available")
def test_foreign_shell_data_forwards_stderr_on_failure_without_show_output(
    capfd, xession
):
    """Issue #4977: a non-zero exit from the foreign shell must surface its
    stderr to the user even when ``show_output`` is left at its default."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as script:
        # ``set -e`` is prepended by xonsh; ``return 1`` exits the sourced
        # script (and therefore the whole subprocess) with code 1, exactly
        # like a real-world rc-file early-exit guard.
        script.write("echo why-it-failed 1>&2\nreturn 1\n")
        script_name = script.name
    try:
        env, aliases = foreign_shell_data(
            shell="bash",
            currenv=(("PATH", os.environ.get("PATH", "")),),
            interactive=False,
            sourcer="source",
            prevcmd=f"source {script_name}",
            files=(script_name,),
        )
    finally:
        os.unlink(script_name)
        foreign_shell_data.cache_clear()

    captured = capfd.readouterr()
    assert env is None and aliases is None
    # The shell's stderr ("why-it-failed") must appear regardless of
    # ``show_output`` — that's the whole point of the fix.
    assert "why-it-failed" in captured.err


@skip_if_on_windows
def test_foreign_shell_data_missing_binary_emits_named_error(
    capfd, xession, monkeypatch
):
    """Issue #4977: when the foreign shell binary itself isn't on PATH the
    user gets a concrete "foreign shell not found" message naming the
    binary, instead of the caller's generic "failed to source"."""
    from xonsh import foreign_shells

    def fake_run(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "bash")

    monkeypatch.setattr(foreign_shells.subprocess, "run", fake_run)
    foreign_shells.foreign_shell_data.cache_clear()
    try:
        env, aliases = foreign_shells.foreign_shell_data(
            shell="bash",  # canon-name check passes; subprocess.run is mocked
            currenv=(("PATH", "/nonexistent"),),
            interactive=False,
            sourcer="source",
            prevcmd="source /tmp/whatever",
        )
    finally:
        foreign_shells.foreign_shell_data.cache_clear()

    captured = capfd.readouterr()
    assert env is None and aliases is None
    assert "foreign shell not found" in captured.err
    assert "'bash'" in captured.err


# ---------------------------------------------------------------------------
# Issue #5894: ``source-foreign /bin/sh /etc/profile`` used to crash with
# ``KeyError: '/bin/sh'`` because POSIX ``sh`` was missing from
# CANON_SHELL_NAMES, and the lookup raised an unhandled exception that
# bubbled up through ProcProxyThread. The fix:
# - Adds ``sh`` / ``/bin/sh`` / ``/usr/bin/sh`` to CANON_SHELL_NAMES with
#   POSIX-safe defaults (``.`` as sourcer, no funcscmd, ``alias`` without
#   the zsh-only ``-L`` flag).
# - Converts the unknown-shell error into a safe-handled failure under
#   the default ``safe=True``, matching every other failure path.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shell_name",
    [
        "sh",
        "/bin/sh",
        "/usr/bin/sh",
        # ``dash`` and ``ash`` are strict-POSIX shells that share the
        # same defaults — they're aliased to the ``sh`` canon key so
        # ``source-foreign dash /file`` works without --sourcer.
        "dash",
        "/bin/dash",
        "/usr/bin/dash",
        "ash",
        "/bin/ash",
        "/usr/bin/ash",
        # ksh family — POSIX-compatible at the env/alias level; their
        # shell-specific function listing isn't exposed, but the common
        # ``source-ksh /etc/ksh.kshrc`` use case works via this alias.
        "ksh",
        "/bin/ksh",
        "/usr/bin/ksh",
        "mksh",
        "/bin/mksh",
        "/usr/bin/mksh",
        "pdksh",
        "/bin/pdksh",
        "/usr/bin/pdksh",
    ],
)
def test_sh_canonicalizes_to_posix_defaults(shell_name):
    """All POSIX-sh spellings (sh/dash/ash/ksh/mksh/pdksh, bare and
    absolute) resolve to the same canon key and pull in POSIX-safe
    defaults (no bash/zsh-specific syntax)."""
    from xonsh.foreign_shells import (
        CANON_SHELL_NAMES,
        DEFAULT_ALIASCMDS,
        DEFAULT_FUNCSCMDS,
        DEFAULT_SETERRPREVCMD,
        DEFAULT_SOURCERS,
    )

    # The mapping is keyed on either the literal shell or its basename;
    # both forms must land on ``"sh"`` so unknown absolute paths like
    # ``/bin/sh`` don't crash. ``os.path.basename("sh") == "sh"``.
    assert CANON_SHELL_NAMES.get(shell_name) == "sh" or (
        CANON_SHELL_NAMES.get(os.path.basename(shell_name)) == "sh"
    )
    # POSIX sourcer is ``.`` — ``source`` is a bash/zsh extension and is
    # rejected by dash, which is /bin/sh on Debian/Ubuntu/Alpine.
    assert DEFAULT_SOURCERS["sh"] == "."
    # No portable way to list functions in POSIX sh; leave empty so the
    # COMMAND template doesn't try to run bash-specific ``declare -F``.
    assert DEFAULT_FUNCSCMDS["sh"] == ""
    # POSIX ``alias`` only — no ``-L`` flag (zsh-only).
    assert DEFAULT_ALIASCMDS["sh"] == "alias"
    # ``set -e`` is POSIX.
    assert DEFAULT_SETERRPREVCMD["sh"] == "set -e"


@skip_if_on_windows
@pytest.mark.skipif(not os.path.exists("/bin/sh"), reason="/bin/sh not present")
def test_foreign_shell_data_sources_via_bin_sh(capfd, xession):
    """End-to-end: sourcing a real script through ``/bin/sh`` populates
    env (and crucially does not crash, fixing issue #5894)."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as script:
        script.write("FROM_PROFILE_SH=ok; export FROM_PROFILE_SH\n")
        script_name = script.name
    try:
        env, _ = foreign_shell_data(
            shell="/bin/sh",
            currenv=(("PATH", os.environ.get("PATH", "")),),
            interactive=False,
            sourcer=".",
            prevcmd=f". {script_name}",
            files=(script_name,),
            safe=False,
        )
    finally:
        os.unlink(script_name)
        foreign_shell_data.cache_clear()

    assert env is not None
    assert env.get("FROM_PROFILE_SH") == "ok"


def test_foreign_shell_data_unknown_shell_safe_returns_none(capfd, xession):
    """Issue #5894: ``safe=True`` (the default) must not raise on an
    unknown shell name — it should print a clean message and return
    ``(None, None)`` so the source-foreign caller's friendly error
    takes over instead of a raw traceback."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    try:
        env, aliases = foreign_shell_data(
            shell="/opt/fish/bin/fish",
            currenv=(),
            interactive=False,
            sourcer="source",
            prevcmd="source /tmp/whatever",
        )
    finally:
        foreign_shell_data.cache_clear()

    captured = capfd.readouterr()
    assert env is None and aliases is None
    assert "unknown foreign shell" in captured.err
    assert "/opt/fish/bin/fish" in captured.err
    # The message must list the canonical shells the user *can* choose.
    assert "bash" in captured.err
    assert "sh" in captured.err
    assert "zsh" in captured.err


def test_foreign_shell_data_unknown_shell_unsafe_raises(xession):
    """With ``safe=False`` the historical KeyError behavior is preserved
    for callers that explicitly opted out of safe handling (so existing
    integrations don't silently start swallowing errors)."""
    from xonsh.foreign_shells import foreign_shell_data

    foreign_shell_data.cache_clear()
    with pytest.raises(KeyError, match="Unknown foreign shell"):
        try:
            foreign_shell_data(
                shell="/opt/fish/bin/fish",
                currenv=(),
                interactive=False,
                sourcer="source",
                prevcmd="source /tmp/whatever",
                safe=False,
            )
        finally:
            foreign_shell_data.cache_clear()
