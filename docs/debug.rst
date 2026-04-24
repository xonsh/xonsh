.. _debug:

*****
Debug
*****

Xonsh ships a debugging helper attached to every session as ``@.debug``.
Its main job is to drop into a debugger at the exact call site — like
Python's builtin ``breakpoint()``, but with automatic engine selection,
session-aware fallbacks, and a xonsh-syntax REPL when no external
debugger is installed.

Quick Start
===========

Drop into a debugger at any point in your xonsh code:

.. code-block:: xonsh

    @.debug.breakpoint()

The engine is chosen automatically in priority order:
``pdbp`` → ``ipdb`` → ``pdb`` → ``execer`` → ``eval``.
The first one that is importable (or, for ``execer``, available on the
session) wins.

To force a specific engine for a single call:

.. code-block:: xonsh

    @.debug.breakpoint(engine='pdbp')
    @.debug.breakpoint(engine='ipdb')
    @.debug.breakpoint(engine='pdb')
    @.debug.breakpoint(engine='execer')   # xonsh REPL at the call site
    @.debug.breakpoint(engine='eval')     # plain-Python REPL

Setting the Default Engine
==========================

Set ``$XONSH_DEBUG_BREAKPOINT_ENGINE`` in your ``.xonshrc`` to change the
default used when ``engine`` is not passed (or is ``'auto'``):

.. code-block:: xonsh

    $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'

Allowed values: ``'auto'`` (default), ``'pdbp'``, ``'ipdb'``, ``'pdb'``,
``'execer'``, ``'eval'``.

An explicit argument to ``breakpoint()`` always beats the env var.

Engines
=======

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Engine
     - Description
   * - ``pdbp``
     - `pdbp <https://github.com/mdmintz/pdbp>`_ — enhanced pdb (sticky mode,
       syntax highlighting, ``where``/``u``/``d`` frame hiding). Install with
       ``xpip install pdbp``.
   * - `ipdb <https://github.com/gotcha/ipdb>`_
     - IPython-flavored pdb. Install with ``xpip install ipdb``.
   * - ``pdb``
     - Stdlib ``pdb``. Always available.
   * - ``execer``
     - A REPL at the caller's frame backed by the session's
       :class:`~xonsh.execer.Execer`. Full xonsh syntax is available —
       subprocesses (``ls``, ``$(ls)``), env lookups (``@.env['HOME']``),
       aliases, and ``@.`` attribute access. Raises ``RuntimeError`` if no
       execer is attached to the session.
   * - ``eval``
     - A minimal REPL using plain Python ``eval``/``exec``. Has no
       dependency on a xonsh session — works in detached contexts (scripts,
       tests) the same as inside an interactive shell.

When ``engine='auto'`` resolves to an engine, ``@.debug`` prints a short
banner identifying the choice and a one-line hint about how to continue or
abort, then drops into that engine.

REPL Commands (execer and eval engines)
=======================================

Both ``execer`` and ``eval`` engines start a small REPL at the caller's
frame. The REPL accepts any Python/xonsh expression or statement, and
recognizes the following control commands:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Command
     - Effect
   * - ``c`` / ``cont`` / ``continue``
     - Resume execution after the breakpoint.
   * - ``exit`` / ``quit`` / ``q``
     - Abort execution — raises :class:`xonsh.debug.XonshDebugQuit`, which
       propagates out of the ``breakpoint()`` call and unwinds the stack.
   * - ``EOF`` / ``Ctrl-C``
     - Same as ``continue`` (least destructive default).

Expression results are printed automatically. Statements (assignments,
loops, etc.) run in the caller's frame, so local variables are visible and
modifiable:

.. code-block:: xonsh

    execer> @.env['HOME']
    '/Users/you'
    execer> ls *.py | head -3
    debug.py
    environ.py
    tools.py
    execer> my_local_var = 42
    execer> c

Routing Python's builtin ``breakpoint()`` Through ``@.debug``
============================================================

PEP 553 makes Python's builtin ``breakpoint()`` go through
``sys.breakpointhook``. ``@.debug`` can install a hook that routes every
builtin ``breakpoint()`` call through the same engine as
``@.debug.breakpoint()``:

.. code-block:: xonsh

    # In ~/.xonshrc
    $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'
    @.debug.replace_builtin_breakpoint()

After this, ``breakpoint()`` anywhere in xonsh code — or in any plain
Python module loaded inside the session — drops into the configured engine
at the call site. To restore Python's default behavior:

.. code-block:: python

    import sys
    sys.breakpointhook = sys.__breakpointhook__


Python API Reference
====================

.. currentmodule:: xonsh.debug

.. autoclass:: XonshDebug
   :members: breakpoint, replace_builtin_breakpoint

.. autoexception:: XonshDebugQuit
