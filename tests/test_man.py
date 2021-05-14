# -*- coding: utf-8 -*-
import os
import pytest  # noqa F401
from xonsh.completers.man import complete_from_man

from tools import skip_if_on_windows

from xonsh.parsers.completion_context import (
    CompletionContext,
    CommandContext,
    CommandArg,
)


@skip_if_on_windows
def test_man_completion(monkeypatch, tmpdir, xession):
    tempdir = tmpdir.mkdir("test_man")
    monkeypatch.setitem(
        os.environ, "MANPATH", os.path.dirname(os.path.abspath(__file__))
    )
    xession.env.update({"XONSH_DATA_DIR": str(tempdir)})
    completions = complete_from_man(
        CompletionContext(
            CommandContext(args=(CommandArg("yes"),), arg_index=1, prefix="--")
        )
    )
    assert "--version" in completions
    assert "--help" in completions
