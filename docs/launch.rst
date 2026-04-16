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


.. _launch-fg-takeover:

Controlling Terminal and Foreground Process Group
==================================================

At startup xonsh performs the industry-standard handshake used by interactive shells
to install itself as the foreground process group of its controlling terminal.

On POSIX, the first thing :func:`xonsh.main.main` does — before argument
parsing, xontrib loading, or xonshrc execution — is call
:func:`xonsh.main._setup_controlling_terminal`. This function installs a
Python-level no-op handler for ``SIGTTIN`` and ``SIGTTOU`` on every POSIX
invocation. If ``os.isatty(stderr)`` is true, it then calls
:func:`xonsh.main._acquire_controlling_terminal`; otherwise it returns after
installing the handlers.

``_acquire_controlling_terminal`` uses stderr (file descriptor 2) as the TTY
handle, matching :func:`xonsh.procs.jobs.give_terminal_to`. It blocks
``SIGTTOU``, ``SIGTTIN``, ``SIGTSTP``, and ``SIGCHLD`` in the calling thread
with ``pthread_sigmask``. If the TTY's foreground group is already the current
process group, it short-circuits to success without registering an ``atexit``
restorer. Otherwise it calls ``setpgid(0, 0)`` followed by
``tcsetpgrp(tty_fd, getpgrp())``, remembers the previous foreground group, and
records the success. The signal mask is restored in a ``finally`` block.

Control returns to ``_setup_controlling_terminal``, which branches on the
result. On success, the Python no-op handlers stay in place, and
:func:`xonsh.main._release_controlling_terminal` is registered with
:mod:`atexit` only when foreground ownership was actually transferred. On
failure, the Python no-op handlers are replaced with ``SIG_IGN`` for
``SIGTTIN`` and ``SIGTTOU``. ``_setup_controlling_terminal`` is idempotent and
is also called from the top of :func:`xonsh.main.main_xonsh`, with the second
call short-circuiting on the ``_tty_setup_done`` module flag.

On shutdown, if the ``atexit`` restorer was registered,
``_release_controlling_terminal`` calls ``tcsetpgrp`` to hand the previous
foreground group back to the parent shell with ``SIGTTOU`` blocked during the
call. If the parent has already reclaimed the TTY, or if the fd is no longer
valid, the error is swallowed. In every other case — no handshake ran, the
fast path was taken, or the handshake failed — the restorer is a no-op.

When the handshake is a no-op
------------------------------

The handshake itself is skipped, though the Python no-op handlers for
``SIGTTIN`` and ``SIGTTOU`` are still installed, on Windows; in non-interactive
invocations where stderr is not a TTY, such as ``xonsh script.xsh``, piped
input, redirected stderr, script-from-stdin mode, and pytest runs that capture
stderr via a pipe; when xonsh is a session leader (``getsid(0) == getpid()``);
when xonsh is already the foreground group, in which case the fast path
returns and the ``atexit`` restorer is not registered; and when
``pthread_sigmask`` is not available on the platform.

Disabling the handshake
------------------------

Set ``XONSH_NO_FG_TAKEOVER=1`` in the parent environment (before launching
xonsh) to skip the handshake entirely. When the handshake is disabled, xonsh
falls back to installing ``SIG_IGN`` for ``SIGTTIN`` and ``SIGTTOU``.

.. code-block:: bash

    # disable the takeover
    XONSH_NO_FG_TAKEOVER=1 xonsh


See also
========

* :doc:`xonshrc` -- RC file loading and configuration snippets
* :doc:`env` -- environment variables and type system
* :doc:`envvars` -- full list of environment variables
