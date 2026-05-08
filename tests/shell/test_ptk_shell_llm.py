"""LLM-generated tests for the prompt_toolkit shell."""

import pytest


def test_singleline_eoferror_propagates(ptk_shell):
    """Regression test for https://github.com/xonsh/xonsh/issues/6412

    ``EOFError().args`` is ``()`` (an empty tuple, not ``None``), so the
    ``getattr(e, "args", (None,))[0]`` guard around the EINTR retry used
    to fall through to ``()[0]`` and raise ``IndexError``. With
    ``$IGNOREEOF=True`` this turned every Ctrl+D into a launch-time
    crash. ``singleline()`` must let ``EOFError`` reach ``cmdloop``,
    which is the layer that prints "Use \"exit\" to leave the shell."
    """
    _, _, shell = ptk_shell

    def raise_eof(**_):
        raise EOFError()

    shell.prompter.prompt = raise_eof
    with pytest.raises(EOFError):
        shell.singleline()


def test_singleline_retries_on_eintr(ptk_shell):
    """``InterruptedError`` (``OSError`` with ``errno==EINTR``) raised
    by prompt_toolkit's ``raw_mode()`` ``tcsetattr`` call when a signal
    arrives during terminal setup must be retried transparently — this
    is the original behavior PR #6192 introduced. Narrowing the
    ``except`` to ``InterruptedError`` (issue #6412) must not regress
    it.
    """
    _, _, shell = ptk_shell
    calls = {"n": 0}

    def flaky(**_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise InterruptedError(4, "Interrupted system call")
        return "echo ok"

    shell.prompter.prompt = flaky
    assert shell.singleline() == "echo ok"
    assert calls["n"] == 2
