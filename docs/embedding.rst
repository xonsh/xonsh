.. _embedding:

***************
Embedding Xonsh
***************

.. warning::

    This page is a **work-in-progress stub**. It currently documents
    only the controlling-terminal handshake for embedded use cases.
    A fuller guide — covering :func:`xonsh.main.setup`, custom
    :class:`~xonsh.shell.Shell` subclasses, teardown, thread safety,
    and integration patterns for LLM agents / TUI apps / REPLs —
    will appear in a later release. If you are embedding xonsh and
    need guidance that is not covered here, please open an issue or
    discussion on GitHub.

Xonsh exposes itself as a Python library in addition to the standalone
``xonsh`` command. Third-party projects can create a xonsh session,
load xontribs and rc files, and drive the execer / shell from their
own code. The public entry point for this is :func:`xonsh.main.setup`,
documented in :mod:`xonsh.main`.


Controlling Terminal Handshake for Embedded Interactive Shells
==============================================================

When xonsh runs as the standalone ``xonsh`` command, its entry point
(:func:`xonsh.main.main`) automatically performs a startup handshake
that makes xonsh the *foreground process group* of its controlling
terminal. This avoids a class of startup crashes and hangs in
environments where the parent process does not arrange TTY ownership
correctly — Flatpak / Bubblewrap sandboxes, build systems, nested
containers, ``systemd --user`` services, some IDE terminals.

See :ref:`launch-fg-takeover` for the full rationale, the failure
modes it fixes (``BlockingIOError`` on asyncio wakeup pipe,
``termios.error`` EINTR, and related), the three-step signal policy,
and the ``XONSH_NO_FG_TAKEOVER`` escape hatch.

When the handshake runs
-----------------------

The handshake is invoked automatically on **both** of these paths:

* :func:`xonsh.main.main` — the default CLI entry point.
* :func:`xonsh.main.main_xonsh` — the inner entry point used when
  some code paths bypass ``main``.

It is **not** invoked from :func:`xonsh.main.setup`. That means an
embedded project that builds its own interactive shell by calling
``setup()`` (or by instantiating :class:`~xonsh.shell.Shell`,
:class:`~xonsh.execer.Execer` and :class:`~xonsh.built_ins.XonshSession`
directly) will **not** get the handshake for free. If your embedded
xonsh runs in one of the affected environments, you need to invoke
it yourself.

How to invoke it from embedded code
-----------------------------------

The helper currently lives in ``xonsh.main`` as a module-private
function: ``_setup_controlling_terminal``. It is private by
convention (leading underscore) but the implementation is stable and
idempotent. A future release is expected to expose a public alias;
until then, calling the private function directly is the supported
path.

Call it **before** you start your interactive shell loop — ideally as
early in your program's startup as possible, so that any xonshrc or
xontrib code your embedder runs already has foreground ownership:

.. code-block:: python

    # embedded_launcher.py
    from xonsh.main import setup
    from xonsh.main import _setup_controlling_terminal

    # Acquire foreground of controlling TTY (idempotent, safe to
    # call multiple times — only the first call does real work).
    # No-op on Windows, in non-TTY contexts (pytest, piped input,
    # redirected stderr), and when XONSH_NO_FG_TAKEOVER=1 is set.
    _setup_controlling_terminal()

    # Your existing xonsh setup stays unchanged.
    setup(
        shell_type="prompt_toolkit",
        # ... your ctx, env, xontribs, aliases, etc.
    )

    # Your custom shell / REPL / agent loop starts here.

What the helper does
--------------------

The call has three possible outcomes, all handled internally:

1. **Fast path** — xonsh is already the foreground process group
   (standard case when launched from a well-behaved terminal). The
   function short-circuits, installs a Python no-op handler for
   ``SIGTTIN`` / ``SIGTTOU`` as a safety net, and returns.
2. **Full handshake** — xonsh transfers TTY foreground ownership to
   its own process group via ``setpgid(0, 0)`` plus
   ``tcsetpgrp(tty, getpgrp())``. Registers an :mod:`atexit`
   restorer so the previous foreground group is handed back on
   process exit.
3. **Sandbox fallback** — if the handshake cannot complete (exotic
   sandbox, cross-session TTY, missing ``CAP_SYS_ADMIN`` for
   certain cases), the no-op handler installed in step 1 is
   *replaced* with ``SIG_IGN`` so that the kernel drops
   ``SIGTTIN`` / ``SIGTTOU`` at delivery time and they never reach
   Python's asyncio wakeup pipe.

All outcomes are safe; every error path degrades cleanly. The helper
never raises under normal use.

When you should *not* call it
-----------------------------

* **Headless embedding.** If your embedder uses
  ``setup(shell_type="none")`` (the default) and never starts an
  interactive prompt, you do not need the handshake. There is no
  TTY to acquire. Calling the helper in this case is harmless (it
  will fall into the non-TTY gate and do nothing), but it is also
  pointless.
* **You manage TTY / job control yourself.** If your embedder
  deliberately keeps xonsh in the background of its controlling
  TTY — for example, you run xonsh under a PTY proxy that
  multiplexes multiple children — taking foreground ownership will
  break your design. Set ``XONSH_NO_FG_TAKEOVER=1`` in the
  environment before starting xonsh, or simply skip the call.
* **You are running tests.** Most test runners capture stderr, in
  which case the helper's internal ``isatty`` gate makes the call a
  no-op. If you use ``pytest -s`` and really want the handshake
  disabled for tests, export ``XONSH_NO_FG_TAKEOVER=1`` for the
  test session.

