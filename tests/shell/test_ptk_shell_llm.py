"""LLM-generated tests for the prompt_toolkit shell."""

import importlib

import pytest


@pytest.fixture
def restore_vt100_cpr():
    """Snapshot Vt100_Output.{ask_for_cpr,responds_to_cpr} and restore
    them after the test. The CPR-suppression patch in ptk_shell runs at
    import time and mutates the class globally, so tests that
    deliberately trigger it must clean up.

    On CI runners that invoke pytest inside an SSH session (FreeBSD VM),
    ``ptk_shell``'s first import — triggered by some collected test's
    import chain — already runs with ``SSH_TTY``/``SSH_CONNECTION`` set
    and replaces both attributes with the no-op lambda.  Naively
    snapshotting at fixture entry would therefore record the lambda as
    "original" and ``test_ptk_does_not_touch_cpr_outside_ssh`` would
    fail because its assertion expects the truly-original method name.

    Drop any leftover lambda overrides from the class *before* taking
    the snapshot so that ``type(...).__delattr__`` falls back to the
    method body defined in ``prompt_toolkit.output.vt100.Vt100_Output``.
    """
    from prompt_toolkit.output.vt100 import Vt100_Output

    for attr in ("ask_for_cpr", "responds_to_cpr"):
        cur = vars(Vt100_Output).get(attr)
        if cur is not None and getattr(cur, "__name__", "") == "<lambda>":
            try:
                delattr(Vt100_Output, attr)
            except AttributeError:
                pass

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


#
# builtins.input() served through prompt_toolkit (PTKInputHook)
#


@pytest.fixture
def input_hook(xession):
    """A hook wired to a fake tty, with ``builtins.input`` restored after."""
    import builtins

    from xonsh.shells.ptk_shell.input_hook import PTKInputHook

    original = builtins.input
    hook = PTKInputHook()
    yield hook
    builtins.input = original


class FakeStream:
    def __init__(self, tty=True):
        self._tty = tty

    def isatty(self):
        return self._tty


def make_tty(monkeypatch, stdin=True, stdout=True):
    monkeypatch.setattr("sys.stdin", FakeStream(stdin))
    monkeypatch.setattr("sys.stdout", FakeStream(stdout))


def test_input_hook_install_and_restore(input_hook):
    """``install`` swaps ``builtins.input`` and ``restore`` puts the
    original back, byte for byte."""
    import builtins

    original = builtins.input
    input_hook.install()
    assert builtins.input is input_hook
    assert input_hook.installed
    input_hook.restore()
    assert builtins.input is original
    assert not input_hook.installed


def test_input_hook_install_is_idempotent(input_hook):
    """A second ``install`` must not record the hook as its own original —
    that would make ``restore`` leave the hook in place forever."""
    import builtins

    original = builtins.input
    input_hook.install()
    input_hook.install()
    input_hook.restore()
    assert builtins.input is original


def test_input_hook_restore_keeps_a_foreign_hook(input_hook):
    """If something else replaced ``input`` after us (a xontrib, ``pdb``,
    user code), ``restore`` must not clobber it."""
    import builtins

    input_hook.install()
    foreign = lambda prompt="": "foreign"  # noqa: E731
    builtins.input = foreign
    input_hook.restore()
    assert builtins.input is foreign


def test_input_hook_reads_through_ptk(input_hook, monkeypatch, xession):
    """On an interactive terminal the hook reads through prompt_toolkit,
    which is not bound by the terminal's 1024-byte canonical-mode line
    limit (issue behind this hook)."""
    make_tty(monkeypatch)
    token = "x" * 2000
    seen = []
    monkeypatch.setattr(input_hook, "prompt", lambda msg: seen.append(msg) or token)
    input_hook.install()
    assert input("token: ") == token
    assert seen == ["token: "]


def test_input_hook_prompt_argument_matches_builtin(input_hook, monkeypatch, xession):
    """``input()`` takes the prompt positionally and stringifies it;
    no argument means an empty prompt."""
    make_tty(monkeypatch)
    seen = []
    monkeypatch.setattr(input_hook, "prompt", lambda msg: seen.append(msg) or "")
    input_hook.install()
    input()
    input(42)
    input(None)
    assert seen == ["", "42", "None"]


@pytest.mark.parametrize(
    "kwargs", [{"stdin": False}, {"stdout": False}, {"stdin": False, "stdout": False}]
)
def test_input_hook_falls_back_without_a_tty(input_hook, monkeypatch, xession, kwargs):
    """Redirected stdin/stdout means no prompt_toolkit prompt — the
    interpreter's own ``input()`` handles it."""
    make_tty(monkeypatch, **kwargs)
    monkeypatch.setattr(
        input_hook, "prompt", lambda msg: pytest.fail("ptk must not be used")
    )
    input_hook.install()
    input_hook._original = lambda *a: "builtin"
    assert input("p") == "builtin"


def test_input_hook_falls_back_off_main_thread(input_hook, monkeypatch, xession):
    """Callable aliases run in worker threads; prompt_toolkit needs the
    main thread for its event loop and signal handlers."""
    import threading

    make_tty(monkeypatch)
    monkeypatch.setattr(
        input_hook, "prompt", lambda msg: pytest.fail("ptk must not be used")
    )
    input_hook.install()
    input_hook._original = lambda *a: "builtin"
    result = []
    t = threading.Thread(target=lambda: result.append(input("p")))
    t.start()
    t.join()
    assert result == ["builtin"]


def test_input_hook_falls_back_inside_a_running_app(input_hook, monkeypatch, xession):
    """Called from a completer or a key binding, i.e. from inside a
    running prompt_toolkit application — nesting would deadlock."""
    make_tty(monkeypatch)

    class RunningApp:
        is_running = True

    monkeypatch.setattr(
        "prompt_toolkit.application.current.get_app_or_none", lambda: RunningApp()
    )
    monkeypatch.setattr(
        input_hook, "prompt", lambda msg: pytest.fail("ptk must not be used")
    )
    input_hook.install()
    input_hook._original = lambda *a: "builtin"
    assert input("p") == "builtin"


def test_input_hook_disabled_by_env(input_hook, monkeypatch, xession):
    """``$XONSH_PTK_INPUT_HOOK = False`` is honored per call, so it can be
    flipped at runtime."""
    make_tty(monkeypatch)
    xession.env["XONSH_PTK_INPUT_HOOK"] = False
    monkeypatch.setattr(
        input_hook, "prompt", lambda msg: pytest.fail("ptk must not be used")
    )
    input_hook.install()
    input_hook._original = lambda *a: "builtin"
    assert input("p") == "builtin"


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_input_hook_propagates_eof_and_sigint(input_hook, monkeypatch, xession, exc):
    """Ctrl-D and Ctrl-C must raise, exactly as the built-in does — not
    fall back and read a second time."""
    make_tty(monkeypatch)

    def raiser(msg):
        raise exc()

    monkeypatch.setattr(input_hook, "prompt", raiser)
    input_hook.install()
    input_hook._original = lambda *a: pytest.fail("must not fall back")
    with pytest.raises(exc):
        input("p")


def test_input_hook_falls_back_on_ptk_failure(input_hook, monkeypatch, xession):
    """A broken prompt_toolkit prompt must never make ``input()``
    unusable."""
    make_tty(monkeypatch)

    def boom(msg):
        raise RuntimeError("no terminal here")

    monkeypatch.setattr(input_hook, "prompt", boom)
    input_hook.install()
    input_hook._original = lambda *a: "builtin"
    assert input("p") == "builtin"


def test_cmdloop_installs_and_restores_the_hook(ptk_shell, xession):
    """The hook lives exactly as long as the interactive command loop:
    ``cmdloop`` is only reached from ``main_xonsh`` in interactive mode,
    so ``-c``, scripts and piped stdin keep the built-in ``input()``."""
    import builtins

    _, _, shell = ptk_shell
    original = builtins.input
    seen = []
    shell.input_hook.install = lambda: seen.append(builtins.input)
    xession.exit = 0  # loop body never runs
    shell.cmdloop()
    assert seen == [original]  # install was called from cmdloop
    assert builtins.input is original  # and the hook was restored


def test_shell_construction_does_not_touch_input(ptk_shell):
    """Building the shell (as tests and non-interactive runs do) must
    leave ``builtins.input`` alone."""
    import builtins

    _, _, shell = ptk_shell
    assert builtins.input is not shell.input_hook
    assert not shell.input_hook.installed


class FakePromptSession:
    """Records how the hook builds and drives its prompt_toolkit session."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        FakePromptSession.instances.append(self)

    def prompt(self, message, **kwargs):
        self.calls.append((message, kwargs))
        return "answer"


@pytest.fixture
def fake_session(monkeypatch):
    # Reach for the module through ``sys.modules``: ``prompt_toolkit.shortcuts``
    # re-exports a *function* named ``prompt``, which shadows the submodule of
    # the same name for both ``import ... as`` and the dotted-string form.
    import sys

    ptk_prompt = sys.modules["prompt_toolkit.shortcuts.prompt"]
    FakePromptSession.instances = []
    monkeypatch.setattr(ptk_prompt, "PromptSession", FakePromptSession)
    return FakePromptSession


def test_input_hook_enables_auto_suggest(input_hook, fake_session, xession):
    """The ``input()`` prompt gets the same grey history suggestion as the
    command prompt (accepted with the right arrow — prompt_toolkit loads
    those key bindings itself)."""
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

    xession.env["XONSH_PROMPT_AUTO_SUGGEST"] = True
    input_hook.prompt("token: ")
    (message, kwargs) = fake_session.instances[0].calls[0]
    assert message == "token: "
    assert isinstance(kwargs["auto_suggest"], AutoSuggestFromHistory)


def test_input_hook_auto_suggest_follows_env(input_hook, fake_session, xession):
    """``$XONSH_PROMPT_AUTO_SUGGEST`` is read per call, so turning
    suggestions off applies to the very next ``input()``."""
    xession.env["XONSH_PROMPT_AUTO_SUGGEST"] = False
    input_hook.prompt("a: ")
    xession.env["XONSH_PROMPT_AUTO_SUGGEST"] = True
    input_hook.prompt("b: ")
    session = fake_session.instances[0]
    assert session.calls[0][1]["auto_suggest"] is None
    assert session.calls[1][1]["auto_suggest"] is not None


def test_input_hook_reuses_one_session(input_hook, fake_session, xession):
    """Answers accumulate in a single session's history — that history is
    what the suggestion is drawn from — and it is dropped on ``restore``."""
    from prompt_toolkit.history import InMemoryHistory

    input_hook.prompt("a: ")
    input_hook.prompt("b: ")
    assert len(fake_session.instances) == 1
    assert isinstance(fake_session.instances[0].kwargs["history"], InMemoryHistory)
    input_hook.install()
    input_hook.restore()
    input_hook.prompt("c: ")
    assert len(fake_session.instances) == 2  # a fresh, empty history
