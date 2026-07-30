"""Serve the built-in ``input()`` from a prompt_toolkit prompt.

CPython's ``input()`` only gets line editing when the ``readline`` module
has been imported: importing it installs ``PyOS_ReadlineFunctionPointer``,
which ``input()`` calls whenever stdin and stdout are interactive. The
prompt_toolkit shell never imports ``readline``, so ``input()`` falls back
to a plain read from the terminal in canonical mode. There the kernel
assembles the line and caps it at ``MAX_CANON`` — 1024 bytes on macOS and
the BSDs, 4096 on Linux. Everything past the cap is discarded, *including*
the terminating newline, so the read never completes and the call hangs
until the user interrupts it. ``getpass.getpass()`` has the same problem:
it clears ``ECHO`` but leaves canonical mode on.

Routing ``input()`` through prompt_toolkit puts the terminal in raw mode
for the duration of the read, which removes the limit and adds the usual
line editing, kill/yank and history keys.

The hook is installed only while the interactive prompt_toolkit shell is
running its command loop (see ``PromptToolkitShell.cmdloop``), and it hands
the call back to the original ``input()`` whenever a prompt_toolkit prompt
cannot be driven safely — off the main thread, without a terminal, or
while another prompt_toolkit application already owns the screen.
"""

import builtins
import sys
import threading

from xonsh.built_ins import XSH

_NOT_GIVEN = object()


class PTKInputHook:
    """Callable replacement for ``builtins.input``.

    Parameters
    ----------
    shell : PromptToolkitShell
        The shell that owns this hook. Only used to read the editing mode,
        so the ``input()`` prompt matches the shell's key bindings.
    """

    def __init__(self, shell=None):
        self.shell = shell
        self.installed = False
        self._original = None
        self._session = None

    def install(self):
        """Replace ``builtins.input`` with this hook."""
        if self.installed:
            return
        self._original = builtins.input
        builtins.input = self
        self.installed = True

    def restore(self):
        """Put the original ``builtins.input`` back."""
        if not self.installed:
            return
        # Someone may have replaced ``input`` after us (a xontrib, ``pdb``,
        # user code). Their hook wins — dropping ours on the floor is better
        # than clobbering theirs.
        if builtins.input is self:
            builtins.input = self._original
        self.installed = False
        self._session = None

    def usable(self):
        """Whether a prompt_toolkit prompt can be driven right now."""
        # Undeclared on purpose: an escape hatch, not a documented setting.
        if not XSH.env.get("XONSH_PTK_INPUT_HOOK", True):
            return False
        # prompt_toolkit needs the main thread: it installs signal handlers
        # and runs an event loop. Callable aliases execute in worker threads.
        if threading.current_thread() is not threading.main_thread():
            return False
        try:
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                return False
        except (AttributeError, OSError, ValueError):
            # Detached, closed or replaced streams.
            return False
        from prompt_toolkit.application.current import get_app_or_none

        app = get_app_or_none()
        if app is not None and app.is_running:
            # Called from a completer, a key binding or a prompt formatter,
            # i.e. from inside a running application. Nesting would deadlock.
            return False
        return True

    def prompt(self, message):
        """Read one line through a dedicated prompt_toolkit session."""
        if self._session is None:
            from prompt_toolkit.enums import EditingMode
            from prompt_toolkit.history import InMemoryHistory
            from prompt_toolkit.shortcuts.prompt import PromptSession

            editing_mode = (
                EditingMode.VI if XSH.env.get("VI_MODE") else EditingMode.EMACS
            )
            # A session of its own, never the shell's: reusing the session
            # that drives the command prompt hangs, and answers to ``input()``
            # have no business in the command history.
            self._session = PromptSession(
                history=InMemoryHistory(), editing_mode=editing_mode
            )
        # Grey fish-style suggestion from earlier answers, accepted with the
        # right arrow — the same mechanic as the command prompt, honoring the
        # same setting. ``PromptSession`` loads the key bindings that accept a
        # suggestion on its own. Read per call so the setting can be flipped
        # while the session is running.
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

        auto_suggest = (
            AutoSuggestFromHistory()
            if XSH.env.get("XONSH_PROMPT_AUTO_SUGGEST")
            else None
        )
        return self._session.prompt(message, auto_suggest=auto_suggest)

    def __call__(self, prompt=_NOT_GIVEN, /):
        """Read a line, matching the semantics of the built-in ``input()``."""
        if not self.usable():
            if prompt is _NOT_GIVEN:
                return self._original()
            return self._original(prompt)
        try:
            return self.prompt("" if prompt is _NOT_GIVEN else str(prompt))
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D / Ctrl-C: the built-in raises these too.
            raise
        except Exception:
            # A broken prompt_toolkit prompt must never make ``input()``
            # unusable — fall back to the interpreter's own implementation.
            if prompt is _NOT_GIVEN:
                return self._original()
            return self._original(prompt)
