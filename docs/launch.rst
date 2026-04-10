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


Running from a Bash Script
==========================

If you want to run interactive xonsh from a bash script you need to have
an interactive shebang (i.e. ``#!/bin/bash -i``) to avoid suspending by
the OS.


See also
========

* :doc:`xonshrc` -- RC file loading and configuration snippets
* :doc:`env` -- environment variables and type system
* :doc:`envvars` -- full list of environment variables
