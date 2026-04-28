.. _debug:

*****
Debug
*****

Xonsh supports two complementary ways to debug xonsh code:

* **Debug in IDE** — attach a full graphical debugger from an editor like
  VS Code.
* **Instant debugging** — drop into a debugger at the exact call site with
  ``@.debug``, with automatic engine selection and a xonsh-syntax REPL
  when no external debugger is installed.

Debug in IDE
============

Xonsh extension for VS Code provides syntax highlighting and basic language support for ``.xsh`` files.
Install via the extensions menu.

Instant debugging
=================

When you need to stop execution at a specific call site without wiring up
an IDE, xonsh ships a debugging helper attached to every session as
``@.debug``. It works like Python's builtin ``breakpoint()``, but with
automatic engine selection, session-aware fallbacks, and a xonsh-syntax
REPL when no external debugger is installed.

Quick Start
-----------

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
--------------------------

Set ``$XONSH_DEBUG_BREAKPOINT_ENGINE`` in your :doc:`xonsh RC <xonshrc>` to
change the default used when ``engine`` is not passed (or is ``'auto'``):

.. code-block:: xonsh

    $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'

Allowed values: ``'auto'`` (default), ``'pdbp'``, ``'ipdb'``, ``'pdb'``,
``'execer'``, ``'eval'``.

An explicit argument to ``breakpoint()`` always beats the env var.

Wrapping breakpoint() in a helper
---------------------------------

If you build your own dev-helper that calls ``@.debug.breakpoint()`` for
you, the debugger would normally stop *inside* the helper, which is
rarely what you want. Pass an explicit ``frame=`` to relocate the stop
site to any frame on the stack — typically the helper's caller. This
mirrors ``pdbp.set_trace(frame=...)``.

.. code-block:: xonshcon

    @ def my_dev_helper():
         print("dropping in…")
         @.debug.breakpoint(frame=@.imp.sys._getframe().f_back)
    @ my_dev_helper()
    dropping in…
    BREAKPOINT WITH 'pdbp'
    # …debugger now sits at my_dev_helper's caller, not inside the helper.

When ``frame=`` is omitted (the default), the debugger uses the
immediate caller's frame, exactly as before.

Engines
-------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Engine
     - Description
   * - ``pdbp``
     - `pdbp <https://github.com/mdmintz/pdbp>`_ — enhanced pdb (sticky mode,
       syntax highlighting, ``where``/``u``/``d`` frame hiding). Install with
       ``xpip install pdbp``.
   * - ``ipdb``
     - `ipdb <https://github.com/gotcha/ipdb>`_ - IPython-flavored pdb. Install with ``xpip install ipdb``.
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

Tab completion in callable aliases
----------------------------------

xonsh runs callable aliases (registered via ``@aliases.register``) in
worker threads. CPython only wires ``readline`` into the main thread, so
the ``pdbp``, ``ipdb``, and ``pdb`` engines lose tab completion when
invoked from inside an alias — the ``TAB`` key inserts a literal tab
into the underlying ``input()`` call instead of triggering completion.

When ``engine='auto'`` is resolved from a non-main thread, ``@.debug``
auto-walks past the readline-based engines and selects ``execer`` (or
``eval`` if no session is attached). Both REPLs use ``input()`` directly
with no completion, so the missing ``TAB`` matches the prompt and there
is no false expectation.

If you set ``$XONSH_DEBUG_BREAKPOINT_ENGINE`` or pass ``engine=`` to one
of the readline-based engines, ``@.debug`` still honours your choice
from a worker thread but prints a :class:`UserWarning` so the broken
``TAB`` is not surprising. The warning is informational — pdbp/ipdb/pdb
still work, just without tab completion.

This is a CPython limitation, not a xonsh bug.

REPL Commands (execer and eval engines)
---------------------------------------

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
-------------------------------------------------------------

PEP 553 makes Python's builtin ``breakpoint()`` go through
``sys.breakpointhook``. ``@.debug`` can install a hook that routes every
builtin ``breakpoint()`` call through the same engine as
``@.debug.breakpoint()``. Add the following to your
:doc:`xonsh RC <xonshrc>`:

.. code-block:: xonsh

    $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'
    @.debug.replace_builtin_breakpoint()

After this, ``breakpoint()`` anywhere in xonsh code — or in any plain
Python module loaded inside the session — drops into the configured engine
at the call site. To restore Python's default behavior:

.. code-block:: python

    import sys
    sys.breakpointhook = sys.__breakpointhook__
