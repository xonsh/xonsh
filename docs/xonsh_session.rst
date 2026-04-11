.. _xonsh_session:

******************************
Xonsh Session
******************************

When xonsh starts, it builds a long-lived **session** object that holds the
environment, history, command pipeline, parser, executor, jobs and so on.
Two Python objects expose this state:

* :class:`xonsh.built_ins.XonshSessionInterface` — a small, **stable** surface
  intended for end users and scripts. Reachable through the
  ``@`` shortcut (``@.env``, ``@.history``, ``@.imp``, ``@.lastcmd``).

* :class:`xonsh.built_ins.XonshSession` — the **internal** session container
  with everything xonsh needs at runtime. Reachable as ``__xonsh__`` (or
  ``xonsh.built_ins.XSH``). Useful when you are extending xonsh, writing
  completers, hooks, or low-level integrations.

This page documents both, with a focus on day-to-day use cases.


``XonshSessionInterface`` and the ``@`` shortcut
================================================

``XonshSessionInterface`` is the **public, narrow** surface of a xonsh session.
It is exposed as a single-character shortcut: the ``@`` token.

Internally, the parser rewrites every ``@.<name>`` into
``__xonsh__.interface.<name>``, so the two are exactly equivalent. ``@`` on
its own evaluates to the interface object itself.

This means you can use ``@`` directly inside Python and subprocess mode:

.. code-block:: xonsh

    # Print the value of $HOME via the typed Env API
    echo @(@.env.get('HOME', '/tmp'))

    # Last exit code
    echo "exit was" @(@.lastcmd.rtn)

    # Inline import + call in one expression
    echo @(@.imp.json.dumps({'ok': True}))

``@.env`` — current environment
-------------------------------

``@.env`` is the current :class:`xonsh.environ.Env` instance. Use it any
time you want a programmatic, typed read or write of an environment
variable, instead of the shell-style ``$VAR`` form.

Use cases:

.. code-block:: xonsh

    # Safe lookup with default
    home = @.env.get('HOME', '/tmp')

    # Temporary override scoped to a `with`-block — restored on exit
    with @.env.swap(EDITOR='vi', PAGER='cat'):
        $[git log --oneline -3]

    # Register a custom env variable with a validator and default
    @.env.register('MY_TIMEOUT', type=int, default=30,
                   doc='Request timeout in seconds.')

``@.env`` shines when the variable name is **dynamic** (built from a
string) and you need default value, since ``$VAR`` requires a literal
name in the source.

``@.history`` — history backend
-------------------------------

``@.history`` is the active :class:`xonsh.history.History` backend
(``json``, ``sqlite``, or ``dummy``). It exposes the same API regardless
of the configured backend.

Use cases:

.. code-block:: xonsh

    # Last command typed in this session (raw input)
    print(@.history.inps[-1])

    # Iterate session items: each is {'inp': cmd, 'ts': (start, end)}
    for item in @.history.items():
        print(item['inp'])

    # All history (across sessions)
    for item in @.history.all_items(newest_first=True):
        print(item['inp'])
        break

    # Force a flush to disk (same as `history flush`)
    @.history.flush()

The ``history`` xonsh command is the user-facing wrapper around this
object. ``@.history`` is what you reach for when you need data, not text.

``@.imp`` — inline importer
---------------------------

``@.imp`` is an :class:`xonsh.built_ins.InlineImporter` instance. It
turns ``@.imp.<module>`` into ``__import__('<module>')`` on first
attribute access, so you can pull in and use a stdlib (or third-party)
module without a separate ``import`` line.

Use cases:

.. code-block:: xonsh

    # One-liners that would otherwise need an import
    echo @(@.imp.time.time())
    echo @(@.imp.json.dumps({'pid': @.imp.os.getpid()}))
    echo @(@.imp.platform.system())

    # Pipe a Python value into a subprocess
    echo @(@.imp.uuid.uuid4()) | tr - _

    # Useful in xonshrc to keep startup imports tidy
    aliases['epoch'] = lambda args: print(int(@.imp.time.time()))

For repeated use of the same module, a regular ``import`` is faster and
clearer; ``@.imp`` is for ad-hoc, one-shot calls where adding an
``import`` would just be noise.

``@.lastcmd`` — last command pipeline
-------------------------------------

``@.lastcmd`` is the :class:`xonsh.procs.pipelines.CommandPipeline` of
the most recently completed subprocess-mode command. It is updated every
time you run a subprocess (``ls``, ``$(...)``, ``![...]``, etc.).

Use cases:

.. code-block:: xonsh

    ls /nope
    print('exit:', @.lastcmd.rtn)        # exit code
    print('stdout:', @.lastcmd.output)   # captured stdout (if any)
    print('stderr:', @.lastcmd.errors)   # captured stderr (if any)
    print('cmd:',    @.lastcmd.cmd)      # the parsed command list
    print('alias:',  @.lastcmd.alias)    # alias resolved (if any)

    # Build a "fail fast" wrapper in a script
    git pull
    if @.lastcmd.rtn != 0:
        raise SystemExit('git pull failed')



``XonshSession`` — the internal session
=======================================

``XonshSession`` is the *full* container that xonsh builds at startup.
It is reachable in two equivalent ways:

* ``__xonsh__`` — bound into ``builtins`` when the session loads, so
  every executed scope sees it as a global.
* ``xonsh.built_ins.XSH`` — the canonical module-level singleton.

.. warning::

    Most attributes here are internal. They are exposed because xonsh
    needs them to talk to itself, but they are **not** part of the
    stable API. Anything in :class:`XonshSessionInterface` (the ``@``
    shortcut) is meant to outlive releases; everything else here may
    change. Prefer ``@.<x>`` or ``XSH.interface`` whenever an equivalent exists.

Useful fields
-------------

The following attributes are the most commonly used by hooks,
completers, and ``xonshrc`` automation. They are listed roughly in the
order you are likely to need them.

* ``__xonsh__.env`` — same :class:`xonsh.environ.Env` as ``@.env``;
  populated by :meth:`XonshSession.load`.

* ``__xonsh__.history`` — same as ``@.history``.

* ``__xonsh__.aliases`` — the live :class:`xonsh.aliases.Aliases`
  mapping. Setting ``__xonsh__.aliases['ll'] = 'ls -la'`` from
  ``xonshrc`` is the canonical way to define an alias. The property
  delegates to ``commands_cache.aliases`` and is read-only on the
  session itself; mutate the mapping in place.

* ``__xonsh__.completers`` — list of registered completer callables.
  Lazily initialized on first access. Modify with the ``completer``
  command or by mutating the list directly.

* ``__xonsh__.shell`` — the active shell wrapper
  (:class:`xonsh.shell.Shell`). The concrete implementation is in
  ``__xonsh__.shell.shell`` (``PromptToolkitShell``, ``ReadlineShell``
  or ``DumbShell``). Use this when you need to call a shell-specific
  method like ``print_color``.

* ``__xonsh__.execer`` — the :class:`xonsh.execer.Execer`, which
  parses, compiles, and runs xonsh source. Use ``execer.exec(src)`` /
  ``execer.eval(src)`` to evaluate xonsh code from inside Python.

* ``__xonsh__.builtins`` — a ``SimpleNamespace`` containing the
  xonsh-injected builtins: ``XonshError``, ``XonshCalledProcessError``,
  ``evalx``, ``execx``, ``compilex``, ``events``, ``print_color``,
  ``printx``.

* ``__xonsh__.ctx`` — the global Python context dict that all xonsh
  user code runs against. Equivalent to ``globals()`` for the REPL.
  Useful for completers and hooks that want to inspect what the user
  has defined.

* ``__xonsh__.all_jobs`` — dict of background jobs keyed by job id.
  See ``jobs``, ``fg``, ``bg``.

* ``__xonsh__.lastcmd`` — same as ``@.lastcmd``.

* ``__xonsh__.sessionid`` — UUID of the current session, used in
  history filenames and similar.

* ``__xonsh__.rc_files`` — list of ``xonshrc`` files actually loaded.

* ``__xonsh__.builtins.events`` — the
  :class:`xonsh.events.events` registry; how you subscribe to
  ``on_postcommand``, ``on_pre_prompt``, ``on_chdir`` and friends.

* ``__xonsh__.exit`` — set this to an integer from anywhere to ask
  xonsh to exit on the next loop iteration with that return code.


Lifecycle and helpers
---------------------

These are the methods you call when *embedding* xonsh, hot-reloading
the session in tests, or writing tooling that wraps it:

* ``load(execer=None, ctx=None, inherit_env=True, **kwargs)`` — fully
  initialize the session: build the env, install builtins into Python,
  hook ``atexit`` for history flush, install signal handlers. Called
  by ``main.main_xonsh`` once at startup.
* ``unload()`` — reverse of ``load``: undo env replacement, restore
  Python's ``exit``/``quit``, flush history, remove ``__xonsh__`` from
  builtins.
* ``link_builtins()`` / ``unlink_builtins()`` — rebind the proxy
  builtins (``XonshError``, ``events``, etc.) into Python's
  ``builtins`` namespace. Used internally by ``load``/``unload``.
* ``cmd(*args, **kwargs)`` — return a :class:`xonsh.built_ins.Cmd`
  *builder* that lets you compose a subprocess pipeline programmatically
  before dispatching it. See the next section.

Subprocess dispatchers — how ``$()``, ``!()``, ``$[]``, ``![]`` map to Python
----------------------------------------------------------------------------

Every subprocess-mode operator in xonsh is a thin parser sugar around a
``XonshSession.subproc_*`` method. Knowing the mapping is what lets you
*construct commands programmatically* (for example from a list of
arguments) and still get exactly the same semantics as the literal form.

.. list-table::
   :header-rows: 1
   :widths: 12 28 30 30

   * - Syntax
     - Method
     - Returns
     - Use it when
   * - ``$(cmd)``
     - ``__xonsh__.subproc_captured_stdout``
     - ``str`` (or ``list[str]`` if ``$XONSH_SUBPROC_OUTPUT_FORMAT='list_lines'``)
     - You only want the captured **stdout** as a value to assign,
       interpolate, or pass on.
   * - ``!(cmd)``
     - ``__xonsh__.subproc_captured_object``
     - :class:`xonsh.procs.pipelines.CommandPipeline`
     - You want the **whole result object**: exit code, stdout, stderr,
       timing, alias info. Truthy iff ``rtn == 0``.
   * - ``$[cmd]``
     - ``__xonsh__.subproc_uncaptured``
     - ``None``
     - You want output to go straight to the **terminal** with no
       capture. The "just run it" form.
   * - ``![cmd]``
     - ``__xonsh__.subproc_captured_hiddenobject``
     - :class:`xonsh.procs.pipelines.HiddenCommandPipeline`
     - Like ``!()`` but the object's ``repr`` does **not** dump the
       captured output to the screen. Useful inside hooks/scripts.
   * - ``@$(cmd)``
     - ``__xonsh__.subproc_captured_inject``
     - ``list[str]``
     - You want the captured stdout split via xonsh's lexer (so it
       respects quoting) and spliced as **arguments** into another
       command.

All of these forms accept the same ``cmds`` shape:

* ``cmds`` is a list of "commands", each command being a list of
  argument strings/tuples.
* Multiple commands separated by ``"|"`` form a pipe.
* A trailing ``"&"`` runs the pipeline in the background.

So ``$(ls -la | grep .py)`` becomes
``subproc_captured_stdout(['ls', '-la'], '|', ['grep', '.py'])``.

This is exactly what the :class:`xonsh.built_ins.Cmd` builder produces,
which is why you can write the same pipeline two ways:

.. code-block:: xonsh

    # As literal subprocess sugar
    out = $(git log --oneline -5 | head -3)

    # Or built explicitly via the Cmd helper
    out = (
        @.imp.xonsh.built_ins
        .Cmd(__xonsh__, 'git', 'log', '--oneline', '-5')
        .pipe('head', '-3')
        .out()    # dispatches to subproc_captured_stdout
    )

Other dispatch helpers on the builder map 1:1 to the table above:

* ``Cmd.out()``  → ``$()``  (``subproc_captured_stdout``)
* ``Cmd.run()``  → ``$[]``  (``subproc_uncaptured``)
* ``Cmd.obj()``  → ``!()``  (``subproc_captured_object``)
* ``Cmd.hide()`` → ``![]``  (``subproc_captured_hiddenobject``)

Use the literal forms in interactive code, and the dispatcher /
builder API when the command list is **dynamic** — for example built
from user input, generated in a loop, or driven by config.

Other AST-invoked helpers
-------------------------

A few more attributes on ``__xonsh__`` exist because xonsh's parser
rewrites special syntax into calls on them. You normally do not call
these directly, but it is useful to know they are there:

* ``pathsearch`` / ``globsearch`` / ``regexsearch`` /
  ``regexmatchsearch`` — implement ``p"..."``, ``g"..."``, ``r"..."``
  and ``$VAR`` glob expansion.
* ``glob`` — wrapper used by glob expansion in subproc mode.
* ``expand_path`` — applied to bare path arguments.
* ``call_macro`` / ``enter_macro`` — power xonsh **macro** calls
  (``f!(...)``) and macro context managers.
* ``path_literal`` — backs the ``p"..."`` Path literal syntax.
* ``help`` / ``superhelp`` — back ``obj?`` and ``obj??`` for Python
  objects (the subproc-mode counterparts live in
  ``xonsh.procs.specs`` and ``xonsh.aliases.print_alias_help``).
* ``eval_fstring_field`` — backs xonsh's f-string field evaluation.
* ``list_of_strs_or_callables`` /
  ``list_of_list_of_strs_outer_product`` — flatten the heterogeneous
  argument lists xonsh's parser produces before dispatching to
  subproc.

When in doubt, prefer ``@.<x>`` (``XSH.interface``) for the four stable bits of the API,
and treat everything on ``__xonsh__`` as power-user territory that
should be guarded with try/except and feature checks.
