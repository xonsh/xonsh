.. _subprocess:
.. _subproc_types:

************************************
Subprocess
************************************

Xonsh provides several operators for launching subprocesses, each with
different capturing and blocking behavior. Choosing the right one
depends on whether you need the output, whether the process is
interactive, and what return type you expect.


``$(cmd)`` -- captured stdout
=============================

Runs ``cmd``, captures stdout and returns it as a string. Nothing is
printed to the screen:

.. code-block:: xonsh

    $(whoami)
    # 'user'

    id $(whoami)          # use captured output as an argument
    # uid=501(user) gid=20(staff)

    output = $(echo -e '1\n2\r3 4\r\n5')
    output
    # '1\n2\n3 4\n5\n'

Use :ref:`command decorators <aliases>` to change the return format:

.. code-block:: xonsh

    $(@lines ls /)
    # ['/bin', '/etc', '/home']

    $(@json curl https://example.com/data.json)
    # {'key': 'value'}

See `Command Decorators <aliases.html#command-decorators-decorator-aliases>`_
for the full list (``@lines``, ``@json``, ``@jsonl``, etc.).


``!(cmd)`` -- captured object
=============================

In fact every subprocess command in xonsh is executed through a
:class:`~xonsh.procs.pipelines.CommandPipeline` -- the central object
that manages process execution, piping, stdout/stderr capturing, and
return codes.

``!(cmd)`` operator captures stdout and stderr and returns a
:class:`~xonsh.procs.pipelines.CommandPipeline`. The object is truthy
when the return code is 0, and iterates over lines of stdout.


.. important::

    This operator is **non-blocking** -- it does not wait for the
    process to finish. To get the output, access ``.out``, ``.rtn``,
    call ``.end()``, or convert to ``str``, which forces the process to
    complete.

.. code-block:: xonsh

    r = !(ls /)
    r.output            # '' -- process may not have finished yet
    r.end()             # block until done
    r.output            # 'bin\netc\n...'

    r = !(ls /)
    r.out               # .out forces ending
    # 'bin\netc\n...'

Non-blocking pattern with a worker:

.. code-block:: xonsh

    worker = !(sleep 3)                   # returns immediately
    echo 'doing other work...'
    if worker.rtn == 0:                   # .rtn blocks until done
        echo 'worker finished successfully'

.. note::

    Because the terminal is detached, this operator can only be used for
    **non-interactive** tools. Running ``!(ls | fzf)`` or
    ``!(python -c "input()")`` will cause the process to be suspended by
    the OS. Use ``$(cmd)``, ``$[cmd]``, or ``![cmd]`` for interactive
    tools.


``![cmd]`` -- uncaptured hidden object
======================================

Streams stdout and stderr to the screen and returns a
:class:`~xonsh.procs.pipelines.HiddenCommandPipeline`.
This is the operator used under the hood when you type a plain command
at the interactive prompt (``cmd`` is the same as ``![cmd]``).

.. code-block:: xonsh

    r = ![echo hello]
    # hello                   <- streamed to terminal
    r.returncode
    # 0

The ``.out`` attribute is empty by default. Set
``$XONSH_CAPTURE_ALWAYS = True`` to capture output even in this mode:

.. code-block:: xonsh

    with @.env.swap(XONSH_CAPTURE_ALWAYS=True):
        r = ![echo hello]
        # hello               <- still streamed
        r.out
        # 'hello\n'           <- also captured

Checking return status with the walrus operator:

.. code-block:: xonsh

    if r := ![ls NO]:
        print(f'OK, code: {r.returncode}')
    else:
        print(f'FAIL, code: {r.returncode}')
    # ls: cannot access 'NO': No such file or directory
    # FAIL, code: 2


``$[cmd]`` -- uncaptured
========================

Streams stdout and stderr directly to the terminal and returns ``None``.
The output always goes to the real terminal, even when ``$[cmd]`` is
called from inside a callable alias or other captured context -- the
subprocess inherits the raw OS file descriptors, bypassing any
Python-level redirection.

Use this for interactive or uncapturable processes (e.g. editors):

.. code-block:: xonsh

    ret = $[echo 123]
    # 123    # output directly
    repr(ret)
    # 'None'

    @aliases.register
    def _configure():
        me = $(whoami)
        echo @(me) > /tmp/config
        $[vim /tmp/config]

    configure


``@$(cmd)`` -- captured inject
==============================

Runs ``cmd``, captures stdout, splits it using
:meth:`Lexer.split() <xonsh.parsers.lexer.Lexer.split>`
(shell-aware, respects quoting), and injects the resulting tokens as
separate arguments:

.. code-block:: xonsh

    showcmd @$(echo -e '1\n2\r3 4\r\n5')
    # ['1', '2\r3', '4', '5']

You can use the same function directly to split any command string:

.. code-block:: python

    from xonsh.parsers.lexer import Lexer
    Lexer().split('echo "hello world" file.txt')
    # ['echo', '"hello world"', 'file.txt']


Threading
=========

Xonsh has a threading prediction mechanism that allows it to understand
which commands can be captured. For example, ``echo`` has no interaction
with the user and is capturable. However, some tools have mixed behavior
-- they can be run for either interactive or non-interactive tasks. The
best example is ``ssh``, which allows for remote terminal sessions *and*
executing commands.

To handle different types of tasks, xonsh has the ``@thread`` and
``@unthread`` built-in decorator aliases. If you need to capture the
output from an interactive tool that has a capturable mode, use
``@thread``:

.. code-block:: xonshcon

    @ !(@thread ssh host -T 'echo remote')
    CommandPipeline(output="remote")

Without ``@thread``, ``ssh`` would be predicted as unthreadable (because
it is normally interactive) and the captured operator would not be able
to collect its output.

Conversely, ``@unthread`` forces a command to run in the foreground
without threading -- useful when a normally threadable command needs
terminal access (e.g. entering a password prompt).


Summary table
=============

.. list-table::
    :header-rows: 1
    :widths: 12 10 10 12 12 16 8 20

    * - Operator
      - Blocking
      - Capture stdout
      - Capture stderr
      - TTY input
      - TTY output
      - Raise
      - Returns
    * - ``$(cmd)``
      - yes
      - yes
      - no
      - yes
      - no for thread
      - yes
      - ``str`` (stdout)
    * - ``!(cmd)``
      - no
      - yes for thread
      - yes for thread
      - no
      - no for thread
      - no
      - :class:`~xonsh.procs.pipelines.CommandPipeline`
    * - ``![cmd]``
      - yes
      - no
      - no
      - yes
      - no for threadable
      - yes
      - :class:`~xonsh.procs.pipelines.HiddenCommandPipeline`
    * - ``$[cmd]``
      - yes
      - no
      - no
      - yes
      - yes
      - yes
      - ``None``
    * - ``@$(cmd)``
      - yes
      - yes
      - no
      - yes
      - no for thread
      - yes
      - ``list``

What all this means:

* **Blocking** -- whether xonsh waits for the process to finish before
  continuing.
* **Capture stdout** -- whether stdout is captured into a ``CommandPipeline`` object
  instead of being streamed to the terminal.
* **Capture stderr** -- whether stderr is captured into a ``CommandPipeline`` object.
* **TTY input** -- whether the process receives terminal input (stdin).
  Without it, interactive tools (e.g. ``fzf``, ``vim``) will
  be suspended by the OS.
* **TTY output** -- whether stdout is connected directly to the terminal.
  "no (threadable)" means the stream is redirected for threadable
  processes.
* **Raise** -- whether a non-zero return code raises
  ``CalledProcessError`` (when ``$RAISE_SUBPROC_ERROR`` is ``True``).
* **Returns** -- the Python type of the value returned by the operator.

A **thread** (threadable, capturable) process is one that does not interact with
the user. If an unthreadable process runs with a detached terminal it
will be suspended by the OS automatically.


See also
========

* :doc:`strings` -- how strings and quoting work in subprocess mode
* :doc:`aliases` -- command decorators (``@lines``, ``@json``) and alias definitions
* :doc:`launch` -- command-line options for starting xonsh
* :doc:`tutorial` -- introduction to xonsh
