.. _error_handling:

Subprocess Error Handling
=========================

Xonsh treats shell commands as first-class code.  When a command fails,
you usually want your script to **stop** instead of silently marching
past the failure — the way a Python exception would — but you also want
the flexibility of ``&&``/``||`` short-circuit logic that
the shell is built around.

This page walks through the rules xonsh uses to decide *when* a failing
subprocess raises a ``subprocess.CalledProcessError``, how those rules
interact with pipes, logical operators, captured forms and per-command
decorators, and how the interactive prompt displays (or hides) the
resulting exception.


Chains
------

To describe where exceptions are raised we use the word **chain** for a
grouping of subprocess commands that produces a single result:

* **single chain** — one plain command: ``ls file``
* **pipe chain** — commands joined with ``|``: ``echo 1 | grep 1 | head``
* **logical chain** — commands joined with ``&&``/``||``:
  ``ls file1 || ls file2 || echo gone``

Statements separated by ``;`` or newlines are *independent* chains.
For example, ``echo 1 && echo 2 ; echo 3 ; echo 1 | grep 1`` contains
**three** chains.

Xonsh decides whether to raise *per chain*, not per individual command,
which is what gives ``||``/``&&`` their shell-like rescue semantics:

.. code-block:: xonshcon

    @ ls /no || echo rescued            # one chain, rescued by ||
    ls: cannot access '/no': No such file or directory
    rescued                              # no exception

    @ echo 1 && ls /no && echo never    # one chain, ends on a failing ls
    1
    ls: cannot access '/no': No such file or directory
    # CalledProcessError (the chain as a whole failed)

    @ echo a ; ls /no ; echo b           # three chains; second fails, third never runs
    a
    ls: cannot access '/no': No such file or directory
    # CalledProcessError on the second chain


Environment variables
---------------------

Xonsh exposes three knobs for error handling.  The first two control
**whether** a subprocess failure raises; the third controls **display
of the exception** at the interactive prompt.

``$XONSH_SUBPROC_RAISE_ERROR`` — default ``True``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Raises ``subprocess.CalledProcessError`` when the **final result of a
chain** is a non-zero exit code.  This is the rule that makes xonsh
scripts behave like Python: a failing command stops execution unless
you explicitly rescue it with ``||`` or ``@error_ignore``.

* ``ls /no`` → raises (single chain, failed)
* ``ls /no | grep root`` → raises (pipe chain, final stage failed)
* ``ls /no || echo ok`` → **no** raise (logical chain rescued by ``||``)
* ``echo 1 && ls /no`` → raises (chain ends on failing ``ls``)
* ``(echo 1 && ls /etc) || echo fb`` → no raise (outer ``||`` rescued
  by a successful inner chain)

``$XONSH_SUBPROC_CMD_RAISE_ERROR`` — default ``False``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Raises on **every** failing command regardless of chain context — any
non-zero exit is fatal.  When ``True`` it short-circuits chain
semantics: ``ls /no || echo fb`` would raise on ``ls``, the ``||``
fallback never runs.

Reserved for scripts that really want "fail fast on anything".  The old
name ``$RAISE_SUBPROC_ERROR`` is kept as a deprecated alias that syncs
to ``XONSH_SUBPROC_CMD_RAISE_ERROR``.

``$XONSH_PROMPT_SHOW_SUBPROC_ERROR`` — default ``False``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a **display** flag — it does not change whether an exception
is raised, only whether the **interactive prompt** prints xonsh's
``subprocess.CalledProcessError: ...`` line after the command's own
``stderr``.  The command's own ``stderr`` is always visible because
the subprocess writes it directly to the terminal.

* ``False`` *(default)* — interactive prompt stays quiet after a
  failed command.  You see the command's ``stderr``, the prompt
  returns, and ``$LAST_RETURN_CODE`` reflects the failure.
* ``True`` — restores the historical behavior of printing
  ``subprocess.CalledProcessError: Command '...' returned non-zero
  exit status N.`` under the command's own output.

Non-interactive scripts (``./script.xsh``, ``xonsh -c``) are
**unaffected** — they always show the exception, because in script
mode you usually want to know which line blew up.

The per-command ``@error_raise`` decorator **always** shows the
exception regardless of this flag — it is the explicit per-command
opt-in.


Captured subprocess ``!()`` is the only exemption
--------------------------------------------------

Every subprocess form raises on a non-zero return code by default —
bare commands, ``![...]``, ``$[...]``, ``$(...)``, ``@$(...)``.  The
**only** exception is the full-capture form ``!(...)``: it returns a
``CommandPipeline`` object and xonsh leaves error handling entirely
up to you.

.. code-block:: xonshcon

    @ ls nofile            # exception
    @ $(ls nofile)         # exception
    @ $[ls nofile]         # exception
    @ ![ls nofile]         # exception

    @ !(ls nofile)         # no exception — returns a CommandPipeline

``!(...)`` is designed to be tested directly, because
``CommandPipeline`` is truthy when the command succeeded and falsy
when it failed:

.. code-block:: xonshcon

    @ if !(ls nofile):
          print("found")
      else:
          print("absent")
    absent

If you want a specific ``!(...)`` call to raise anyway, use the
``@error_raise`` decorator inside it — the decorator wins over the
``!()`` exemption:

.. code-block:: xonshcon

    @ if !(@error_raise ls nofile):
          print("found")
    # CalledProcessError — @error_raise overrides the !() exemption


Per-command decorators
----------------------

Two decorator aliases give you an escape hatch that is scoped to a
single command inside a larger chain.

``@error_raise`` — always raise
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Force ``subprocess.CalledProcessError`` on this command, regardless of
``$XONSH_SUBPROC_RAISE_ERROR``, ``$XONSH_SUBPROC_CMD_RAISE_ERROR``, or
whether the command sits inside a normally-rescuing chain:

.. code-block:: xonshcon

    @ @error_raise ls /no || echo fb
    # CalledProcessError — @error_raise wins over ||

    @ !(@error_raise ls /no)
    # CalledProcessError — @error_raise wins over !() exemption too

It also **always** shows the exception at the interactive prompt,
overriding ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR = False``.

``@error_ignore`` — never raise
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The inverse — the command *never* raises, no matter the environment
settings or chain position:

.. code-block:: xonshcon

    @ @error_ignore ls /no
    ls: cannot access '/no': No such file or directory
    # no exception

    @ echo 1 && @error_ignore ls /no && echo 2
      echo 3
    1
    ls: cannot access '/no': No such file or directory
    3
    # no exception; the `@error_ignore` also makes the chain
    # treat the failing ls as "don't raise on this final operand"

``@error_ignore`` is especially handy when you want a command to
contribute to the chain's return code but **not** its error behavior:

.. code-block:: xonshcon

    @ echo 1 | @error_ignore grep pattern | wc -l
    0
    # grep returns 1 (no match), @error_ignore keeps the pipe quiet,
    # wc happily prints 0


Catching the exception
----------------------

The raised exception is a plain ``subprocess.CalledProcessError``, so
the usual Python idioms work:

.. code-block:: xonshcon

    @ import subprocess
    @ try:
          ls /no
      except subprocess.CalledProcessError as e:
          print("rc =", e.returncode)
          print("cmd =", e.cmd)
    ls: cannot access '/no': No such file or directory
    rc = 2
    cmd = ['ls', '/no']

For scoped overrides, ``env.swap`` is often cleaner than catching:

.. code-block:: xonshcon

    @ with @.env.swap(XONSH_SUBPROC_RAISE_ERROR=False):
          ls /no
    ls: cannot access '/no': No such file or directory
    # no exception, even though the default is True

For **captured iteration** there is also ``CommandPipeline.itercheck()``
which raises ``XonshCalledProcessError`` (a subclass of
``subprocess.CalledProcessError`` that additionally carries
``.completed_command`` and ``.stderr``):

.. code-block:: xonshcon

    @ try:
          for line in !(grep -R TODO src/).itercheck():
              print(line.strip())
      except XonshCalledProcessError as e:
          print("grep failed with rc", e.returncode)


Interactive prompt behavior in detail
-------------------------------------

With the default ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR = False``:

.. code-block:: xonshcon

    @ ls /no
    ls: cannot access '/no': No such file or directory
    @ echo $LAST_RETURN_CODE
    2

    @ echo hi && ls /no && echo bye
    hi
    ls: cannot access '/no': No such file or directory
    @

With ``$XONSH_PROMPT_SHOW_SUBPROC_ERROR = True``:

.. code-block:: xonshcon

    @ $XONSH_PROMPT_SHOW_SUBPROC_ERROR = True
    @ ls /no
    ls: cannot access '/no': No such file or directory
    subprocess.CalledProcessError: Command '['ls', '/no']' returned non-zero exit status 2.
    @

``@error_raise`` always shows:

.. code-block:: xonshcon

    @ @error_raise ls /no
    ls: cannot access '/no': No such file or directory
    subprocess.CalledProcessError: Command '['@error_raise', 'ls', '/no']' returned non-zero exit status 2.


See also
--------

* :ref:`tutorial` — the scripting section discusses
  ``$XONSH_SUBPROC_RAISE_ERROR`` in the context of writing robust xonsh
  scripts.
* :ref:`aliases` — for ``@error_raise`` / ``@error_ignore`` and other
  decorator aliases.
