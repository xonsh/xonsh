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
