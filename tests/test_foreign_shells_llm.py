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
        env, aliases = foreign_shell_data(
            shell="bash",
            currenv=(),
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
            currenv=(),
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
