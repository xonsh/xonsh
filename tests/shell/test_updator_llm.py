"""Real callable capture fields offloaded through the PTK prompt executor."""

import sys

import pytest

from tests.built_ins.test_built_ins_llm import (
    capture_interleaving as capture_interleaving,
)
from xonsh.built_ins import subproc_captured_stdout


def test_async_capture_fields(capture_interleaving, ptk_shell, xonsh_session):
    _, _, shell = ptk_shell
    xonsh_session.env["ENABLE_ASYNC_PROMPT"] = True
    formatter = shell.prompt_formatter

    def submit(child):
        fields = {
            "first": lambda: child("first", 0),
            "second": lambda: child("second", 0),
        }
        try:
            xonsh_session.env["PROMPT_FIELDS"].update(fields)
            xonsh_session.env["RIGHT_PROMPT"] = "{first}"
            xonsh_session.env["BOTTOM_TOOLBAR"] = "{second}"
            shell._get_prompt_tokens("RIGHT_PROMPT", "rprompt")
            shell._get_prompt_tokens("BOTTOM_TOOLBAR", "bottom_toolbar")
            prompts = formatter.updator.prompts
            futures = [
                next(iter(prompts[name].futures))
                for name in ("rprompt", "bottom_toolbar")
            ]
            return [future.result(timeout=15) for future in futures]
        finally:
            formatter.updator.executor.thread_pool.shutdown(wait=True)

    assert capture_interleaving(submit=submit) == ["first", "second"]


@pytest.mark.parametrize("direct", [False, True])
def test_synchronous_callable_controls(ptk_shell, xonsh_session, direct):
    _, _, shell = ptk_shell
    xonsh_session.env["ENABLE_ASYNC_PROMPT"] = False
    fields = {
        label: lambda label=label: subproc_captured_stdout(
            [sys.executable, "-c", f"print({label!r})"]
        )
        for label in ("first", "second")
    }
    if direct:
        assert [field() for field in fields.values()] == ["first", "second"]
    else:
        xonsh_session.env["PROMPT_FIELDS"].update(fields)
        assert (
            shell.prompt_formatter("{first}:{second}", threaded=False) == "first:second"
        )
        assert not hasattr(shell.prompt_formatter, "updator")
