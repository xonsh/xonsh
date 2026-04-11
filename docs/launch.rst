.. _launch:

************************************
Launch Options
************************************

Xonsh accepts the following command-line arguments:

.. code-block:: text

    xonsh [-h] [-V] [-c COMMAND] [-i] [-l] [--rc RC [RC ...]]
          [--no-rc] [--no-env] [--no-script-cache] [--cache-everything]
          [-D ITEM] [-st SHELL_TYPE] [--timings]
          [--save-origin-env] [--load-origin-env]
          [script-file] [args ...]

Arguments Reference
===================

``script-file``
    If present, execute the script and exit.

``args``
    Additional arguments passed to the script.

``-h``, ``--help``
    Show help and exit.

``-V``, ``--version``
    Show version information and exit.

``-c COMMAND``
    Run a single command and exit.

``-i``, ``--interactive``
    Force running in interactive mode.

``-l``, ``--login``
    Run as a login shell.

``--rc RC [RC ...]``
    The xonshrc files to load. These may be either xonsh files or
    directories containing xonsh files.

``--no-rc``
    Do not load any xonsh RC files.  ``--rc`` is ignored when
    ``--no-rc`` is set.

``--no-env``
    Do not inherit parent environment variables.

``--no-script-cache``
    Do not cache scripts as they are run.

``--cache-everything``
    Use a cache, even for interactive commands.

``-D ITEM``
    Define an environment variable, in the form ``-DVAR=VAL``, or
    inherit an existing variable with ``-DVAR``.  May be used many
    times.

``-st``, ``--shell-type SHELL_TYPE``
    What kind of shell to use.  Possible values: ``best`` (``b``),
    ``prompt-toolkit`` (``ptk``, ``prompt_toolkit``),
    ``readline`` (``rl``), ``dumb`` (``d``), ``random`` (``rand``).
    Overrides ``$SHELL_TYPE``.

``--timings``
    Print timing information before the prompt is shown.  Useful for
    tracking down performance issues and investigating startup times.

``--save-origin-env``
    Save origin environment variables before running xonsh.  Use with
    ``--load-origin-env`` to restore them later.

``--load-origin-env``
    Load origin environment variables that were saved with
    ``--save-origin-env``.


Clean Environment
=================

Starting xonsh with ``--no-env`` drops the inherited environment, but
a few essential variables (``PATH``, ``TERM``, ``HOME``) will be
missing, which may cause warnings.  Use ``-D`` to pass them through:

.. code-block:: xonsh

    xonsh --no-rc --no-env  # works, but may warn about no TTY or no HOME

    # Create a convenient alias:
    aliases['xonsh-no-env'] = 'xonsh --no-rc --no-env -DPATH -DTERM -DHOME'
    xonsh-no-env


Minimal Startup
===============

For the fastest possible startup with no extras -- useful for scripting,
benchmarking, or debugging -- combine the flags to disable everything:

.. code-block:: xonsh

    xonsh --no-rc --no-env --shell-type readline \
          -DCOLOR_INPUT=0 -DCOLOR_RESULTS=0 -DPROMPT='@ ' \
          -DXONSH_HISTORY_BACKEND=dummy -DXONTRIBS_AUTOLOAD_DISABLED=1

What each flag does:

* ``--no-rc`` -- prevent loading RC files.
* ``--no-env`` -- prevent inheriting the environment.
* ``--shell-type readline`` -- use the cheapest shell backend.
* ``-DCOLOR_INPUT=0`` -- disable input coloring and the file-type
  completer that reads files to choose colors.
* ``-DCOLOR_RESULTS=0`` -- disable colors in output.
* ``-DPROMPT='@ '`` -- use a simple prompt instead of the default one
  with gitstatus and other complex fields.
* ``-DXONSH_HISTORY_BACKEND=dummy`` -- disable the history backend.
* ``-DXONTRIBS_AUTOLOAD_DISABLED=1`` -- skip loading xontribs.


.. _launch-xxonsh:

Launching the Same Xonsh (xxonsh)
=================================

The built-in ``xxonsh`` alias (see :ref:`aliases-xxonsh` for the alias
entry in the Built-in Aliases reference) launches exactly the same
``xonsh`` that was used to start the current session — same interpreter,
same source tree, regardless of the current working directory or whatever
is installed in ``site-packages``.

When another tool needs to spawn xonsh with the same identity as the
current session, use ``get_xxonsh_alias()`` from ``xonsh.aliases``: it
always returns a ``list`` so it can be concatenated with any other argv
list. For example, to start ``tmux`` with exactly this xonsh:

.. code-block:: xonsh

    aliases['xtmux'] = ['tmux', 'new-session'] + @.imp.xonsh.aliases.get_xxonsh_alias()


Save and Load Origin Environment
================================

When you launch a nested xonsh with ``--no-env``, all environment
variables from the parent session are dropped. Sometimes you want a
clean environment for a project but still need the original env with ``PATH``,
``TERM``, and other OS-level variables.

``--save-origin-env`` snapshots the current environment before running xonsh,
and ``--load-origin-env`` restores that snapshot inside the
new session. Together, they let you start a fresh xonsh from the current modified
environment.

For example, suppose you have a main xonsh session and you run
``xonsh --save-origin-env``. You're working, doing things, and then you need
to work with a project that has its own environment setup in ``project_rc.xsh``.
You don't want to source this file to avoid collisions, and you can't run a
xonsh instance with just ``--rc`` because the new session will inherit your current
environment.

In this case, you can run ``xonsh --load-origin-env --rc project_rc.xsh`` and
get a new, clean environment with project-specific aliases, environment variables,
and possibly a custom prompt as well.

After finishing work on that project, you can exit and return to your main environment.


Running from Another Shell
==========================

To launch xonsh from another shell, make sure that shell is itself running
in interactive mode — otherwise the OS will suspend the interactive xonsh
process. For example, when starting xonsh from a bash script, use an
interactive shebang (``#!/bin/bash -i``).


See also
========

* :doc:`xonshrc` -- RC file loading and configuration snippets
* :doc:`env` -- environment variables and type system
* :doc:`envvars` -- full list of environment variables


.. _launch-fg-takeover:

Controlling Terminal and Foreground Process Group
==================================================

When xonsh starts interactively on a POSIX system it performs a small
startup handshake to make itself the *foreground process group* of the
terminal it's attached to. This section explains what that means, why
xonsh bothers, and how to disable it if it conflicts with something in
your environment.

Background: foreground process group
-------------------------------------

Every POSIX terminal has exactly one **foreground process group**.
Processes in that group are allowed to read from and write control
operations to the terminal without being suspended. Processes in any
other group are "in the background" — when they touch the TTY the
kernel sends them ``SIGTTIN`` (background read) or ``SIGTTOU``
(background control / write under ``TOSTOP``), and the default
disposition of those signals is to stop the process, not to let the
operation proceed.

Interactive shells like bash and zsh install themselves as the
foreground group at startup. They do it with a short sequence:

1. Find the controlling TTY's file descriptor.
2. Check whether the current foreground group is already ours.
3. If not, block the signals that would disrupt step 4.
4. Call ``setpgid(0, 0)`` to land in a process group of our own.
5. Call ``tcsetpgrp(tty_fd, getpgrp())`` to install that group as
   the TTY's foreground group.
6. Restore the signal mask.

After this, every TTY touch the shell makes is permitted by the
kernel and the job-control primitives the shell uses to manage
pipelines (``tcsetpgrp``, ``tcsetattr``, …) work as intended.

Why xonsh needs to do the same
------------------------------

Historically xonsh skipped this handshake and relied on whatever
launched it to have arranged things correctly. That assumption holds
when xonsh is started from a typical terminal via a parent shell
(bash, zsh, fish, another xonsh, …), because those shells
``fork + exec + tcsetpgrp`` the child correctly. It breaks in several
common non-typical environments:

* **Flatpak / Bubblewrap** and similar sandbox launchers: ``bwrap``
  does not reassign the TTY's foreground group to the sandboxed
  child. xonsh ends up running as a background process of the TTY.
* **Build systems, CI runners, IDE integrated terminals** and
  service managers such as ``systemd --user`` that launch xonsh via
  ``posix_spawn`` without wiring up job control.
* **Nested containers** that reuse the outer PTY without reconfiguring
  foreground ownership.

In all of these, xonsh is technically a background process of the
TTY. Every terminal operation — ``tcgetattr`` during
``prompt_toolkit`` initialisation, ``tcsetpgrp`` when launching a
pipeline, plain reads and writes when ``TOSTOP`` is set — fires
``SIGTTIN`` or ``SIGTTOU``. There are two failure modes that follow:

1. **asyncio wakeup pipe overflow.** Python routes signals to a
   non-blocking self-pipe so the main event loop can wake up when
   one arrives. If signals arrive faster than the loop drains the
   pipe — which happens instantly under a startup storm — the C-level
   signal handler's write to the pipe fails and raises::

       BlockingIOError: [Errno 11] Resource temporarily unavailable

   xonsh startup crashes.

2. **termios EINTR.** Even when the storm is under control,
   low-frequency signals (``SIGCHLD``, ``SIGWINCH``, …) still arrive
   while ``prompt_toolkit`` calls ``termios.tcsetattr`` to switch the
   terminal into raw mode. The C call returns ``EINTR``, which
   ``tcsetattr`` surfaces as::

       termios.error: (4, 'Interrupted system call')

Users in the affected environments used to work around this by
running xonsh under a wrapper that installed ``SIG_IGN`` for
``SIGTTIN`` / ``SIGTTOU`` before importing xonsh. That works, but
it is a workaround: the kernel still considers xonsh background, job
control is still subtly wrong, ``SIG_IGN`` is inherited through
``exec`` and affects child processes, and the wakeup-pipe race can
still bite if a signal storm recurs after the fallback handler is
re-installed.

What xonsh does now
-------------------

On POSIX, the **very first thing** :func:`xonsh.main.main` does — before
argument parsing, xontrib loading or xonshrc execution — is call
:func:`xonsh.main._setup_controlling_terminal`. That in turn runs the
bash-style handshake in
:func:`xonsh.main._acquire_controlling_terminal` and installs matching
signal handlers. The early placement matters: xonsh's rc files are
arbitrary user code, and a typical ``~/.xonshrc`` will contain
``$(...)``/``!(...)`` subprocess captures, possibly including
interactive programs like ``fzf`` that themselves want to manipulate
the terminal via ``tcsetattr``. If xonsh is already foreground by the
time rc runs, every downstream TTY operation is straightforward; if it
is not, the ``SIG_IGN`` fallback (see below) keeps the asyncio wakeup
pipe from overflowing while rc executes.

The handshake itself (``_acquire_controlling_terminal``):

* Uses **stderr** (file descriptor 2) as the TTY handle. This matches
  :func:`xonsh.procs.jobs.give_terminal_to`, which also uses FD 2 when
  xonsh later transfers the terminal between pipeline groups.
* Aborts cleanly — with no side effects — if any precondition fails:
  Windows, session leader (which cannot ``setpgid`` itself), missing
  ``pthread_sigmask``, or the escape hatch described below.
* Blocks ``SIGTTOU``, ``SIGTTIN``, ``SIGTSTP`` and ``SIGCHLD`` in the
  calling thread with ``pthread_sigmask``. ``SIGTTOU`` is the critical
  one; without the block, ``tcsetpgrp`` below would send ``SIGTTOU``
  to xonsh itself and suspend it immediately.
* Short-circuits to success if the TTY's foreground group is already
  our process group — the handshake is not needed and the restorer is
  *not* registered, so on shutdown we don't race with the parent
  shell's own ``tcsetpgrp``.
* Otherwise calls ``setpgid(0, 0)`` followed by
  ``tcsetpgrp(tty_fd, getpgrp())``, remembers the previous foreground
  group, and records the fact that the handshake succeeded.
* Restores the signal mask in a ``finally`` block so any error path
  leaves the process in a clean state.

``_setup_controlling_terminal`` orchestrates the handshake with a
three-step signal policy:

**Step 1 — always install Python no-op handlers.** On any POSIX
invocation — interactive, script mode, piped input, redirected
stderr, test runner — ``_setup_controlling_terminal`` installs a
Python-level no-op handler for ``SIGTTIN`` and ``SIGTTOU``. This
matches xonsh's historical behavior from before the handshake
existed: script-mode xonsh must not be suspended by default
``SIG_DFL`` when something indirectly touches the TTY, and a Python
handler (rather than ``SIG_IGN``) is preferred because it is *not*
inherited across ``exec``, so subprocess children keep their normal
job control.

**Step 2 — run the handshake when stderr is a real TTY.** If
``os.isatty(stderr)`` is true, ``_setup_controlling_terminal`` calls
:func:`_acquire_controlling_terminal`. Non-TTY callers stop after
step 1; pytest, script mode, and redirected-stderr invocations all
bail out here and keep the step-1 handlers.

**Step 3 — branch on handshake result.** If the handshake succeeded
(either the fast path because we were already foreground, or a full
acquire), the step-1 Python handlers stay in place and
``_setup_controlling_terminal`` registers the ``atexit`` restorer —
but only if we *actually* transferred foreground ownership, so the
fast path leaves no atexit behind and we never race with the parent
shell's own ``tcsetpgrp`` on exit. If the handshake failed — typical
in sandboxes that cannot be made foreground —
``_setup_controlling_terminal`` **replaces** the step-1 Python
handlers with ``SIG_IGN``. That is the sandbox fallback: the kernel
discards ``SIGTTIN`` / ``SIGTTOU`` outright, so they never reach
Python's asyncio wakeup pipe and the ``BlockingIOError`` storm
cannot happen. ``SIG_IGN`` *is* inherited across ``exec``, but in a
sandbox the children have the same TTY ownership problem anyway, so
this is the right default.

``_setup_controlling_terminal`` is idempotent. It is also called from
the top of :func:`xonsh.main.main_xonsh`, so callers that enter the
shell loop without going through ``main`` (tests, programmatic
launches) still end up with the correct signal setup; the second call
in a normal ``main → main_xonsh`` flow short-circuits on the
``_tty_setup_done`` module flag.

Shutdown: handing the TTY back
-------------------------------

When the handshake actually did change the foreground group, xonsh
registers :func:`xonsh.main._release_controlling_terminal` with
:mod:`atexit`. On shutdown this function calls ``tcsetpgrp`` to
restore the previous foreground group — normally the parent shell —
with ``SIGTTOU`` blocked during the call. If the parent has already
reclaimed the TTY, or if the fd is no longer valid, the error is
swallowed: this runs under ``atexit`` and raising would just make
shutdown noisy. In every other case (handshake didn't run, handshake
took the fast path because we were already foreground, handshake
failed), the restorer is a no-op.

When the handshake is a no-op
------------------------------

The *handshake itself* is skipped in these situations (step 1 still
installs the historical Python no-op handlers):

* **Windows.** POSIX controlling terminals do not apply, and
  ``_setup_controlling_terminal`` returns immediately after the
  ``ON_WINDOWS`` check without installing anything.
* **Non-interactive invocations** where stderr is not a TTY:
  ``xonsh script.xsh``, piped input, redirected stderr, script-from-
  stdin mode, and tests under pytest (which captures stderr via a
  pipe). ``_setup_controlling_terminal`` installs the step-1 Python
  handlers and returns — no handshake, no atexit. This matches the
  pre-handshake xonsh behavior for these modes.
* **xonsh is a session leader** (``getsid(0) == getpid()``). A
  session leader cannot change its own process group id, and if it
  is session leader it almost always already owns the TTY. The
  handshake declines and the ``SIG_IGN`` fallback replaces the
  step-1 handlers.
* **xonsh is already the foreground group** — the fast path returns
  immediately, the step-1 Python handlers stay in place as a safety
  net, and the atexit restorer is *not* registered (there is
  nothing to restore).
* **Missing** ``pthread_sigmask``, which is POSIX-only and absent on
  exotic builds.

Disabling the handshake
------------------------

Set ``XONSH_NO_FG_TAKEOVER=1`` in the parent environment (before
launching xonsh) to skip the handshake entirely. This is an escape
hatch for rare cases where taking over the foreground group
conflicts with a parent process that expects xonsh to stay in its
original process group. When the handshake is disabled, xonsh falls
back to installing ``SIG_IGN`` for ``SIGTTIN`` / ``SIGTTOU`` —
exactly the behaviour of the historical sandbox wrapper.

.. code-block:: bash

    # disable the takeover, e.g. when debugging unusual TTY setups
    XONSH_NO_FG_TAKEOVER=1 xonsh

What this does not fix
-----------------------

The handshake addresses the *foreground group* part of the problem.
It does not work around every possible issue that can arise from
running xonsh in an unusual TTY environment:

* If the TTY belongs to a different session than xonsh (for example
  a sandbox that calls ``setsid``), ``tcsetpgrp`` fails with
  ``EPERM`` and the handshake cleanly declines. You are still on
  the ``SIG_IGN`` fallback in that case.
* ``termios.tcsetattr`` calls can still be interrupted by signals
  other than ``SIGTTIN`` / ``SIGTTOU``. In practice a foreground
  xonsh sees far fewer interruptions — most of the signal volume
  was the ``SIGTT*`` storm — so the ``EINTR`` race is dramatically
  less likely, but it is not impossible. If you hit it, wrap your
  launcher to retry ``tcsetattr`` / ``tcgetattr`` on ``EINTR``.
* Stealing a controlling terminal from a different session requires
  ``TIOCSCTTY`` with ``CAP_SYS_ADMIN`` in the init user namespace,
  which is not available in Flatpak or rootless containers. If you
  really need a fresh controlling TTY, run xonsh under a PTY proxy
  such as ``script(1)`` or inside ``tmux``.
