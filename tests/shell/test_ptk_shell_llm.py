"""LLM-generated tests for the prompt_toolkit shell."""

import importlib
import os

import pytest


@pytest.fixture
def restore_vt100_cpr():
    """Snapshot Vt100_Output.{ask_for_cpr,responds_to_cpr} and restore
    them after the test. The CPR-suppression patch in ptk_shell runs at
    import time and mutates the class globally, so tests that
    deliberately trigger it must clean up."""
    from prompt_toolkit.output.vt100 import Vt100_Output

    orig_ask = Vt100_Output.ask_for_cpr
    orig_responds = Vt100_Output.responds_to_cpr
    yield
    Vt100_Output.ask_for_cpr = orig_ask
    Vt100_Output.responds_to_cpr = orig_responds


@pytest.mark.parametrize("ssh_var", ["SSH_TTY", "SSH_CONNECTION"])
def test_ptk_suppresses_cpr_inside_ssh(monkeypatch, ssh_var, restore_vt100_cpr):
    """Inside an SSH session, prompt_toolkit must not issue Cursor
    Position Report (``\\x1b[6n``) queries — see issue #5686.

    The terminal's reply travels back through stdin and is observed by
    the local ssh client's tilde-escape filter; a reply arriving
    between the user's Enter and the following ``~`` resets
    ``last_was_cr`` to 0, so ssh never sees ``\\r~`` and ``~.`` etc.
    silently fail.

    We re-import ``xonsh.shells.ptk_shell`` with the SSH env var set so
    the module-level guard runs, then check that
    ``Vt100_Output.ask_for_cpr`` is the no-op installed by the guard.
    """
    for v in ("SSH_TTY", "SSH_CONNECTION"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv(ssh_var, "/dev/pts/0")

    import xonsh.shells.ptk_shell as ptk_shell_module

    importlib.reload(ptk_shell_module)

    from prompt_toolkit.output.vt100 import Vt100_Output

    # The monkey-patch installs a one-line lambda — both checks
    # together pin down that it really is our no-op.
    assert Vt100_Output.ask_for_cpr.__name__ == "<lambda>"
    # Confirm the responds_to_cpr override is the False-returning
    # property (so renderer code paths skip waiting for a reply).
    assert isinstance(Vt100_Output.responds_to_cpr, property)


def test_ptk_does_not_touch_cpr_outside_ssh(monkeypatch, restore_vt100_cpr):
    """Outside SSH the CPR machinery must be untouched so prompt_toolkit
    can render correctly against the real terminal."""
    for v in ("SSH_TTY", "SSH_CONNECTION"):
        monkeypatch.delenv(v, raising=False)

    import xonsh.shells.ptk_shell as ptk_shell_module

    importlib.reload(ptk_shell_module)

    from prompt_toolkit.output.vt100 import Vt100_Output

    assert Vt100_Output.ask_for_cpr.__name__ != "<lambda>"


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
