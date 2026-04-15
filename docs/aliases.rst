.. _aliases:

********************
Built-in Aliases
********************
This page describes the xonsh built-in commands and aliases.

Well-known commands
====================

``cd``
--------------------
Changes the directory. If no directory is specified (i.e. if there are no arguments)
then this changes to the current user's home directory.


``ls``
--------------------
The ``ls`` command is aliased to ``['ls', '--color=auto', '-v']`` on Linux.  On macOS,
FreeBSD, and DragonFlyBSD it is instead aliased to ``['ls', '-G']``.
On NetBSD and OpenBSD no ``ls`` alias is defined.


``grep``
--------------------
The ``grep`` command is aliased to ``['grep', '--color=auto']``.


``history``
--------------------
Tools for dealing with xonsh history. See `the history tutorial <history.html>`_
for more information all the history command and all of its sub-commands.

.. command-help:: xonsh.history.main.history_main


``timeit``
--------------------
Runs timing study on arguments. Similar to IPython's ``%timeit`` magic.


``EOF``, ``exit``, and ``quit``
----------------------------------
The commands ``EOF``, ``exit``, and ``quit`` all alias the same action, which is to
leave xonsh in a safe manner. Typing ``Ctrl-d`` is the same as typing ``EOF`` and
pressing enter.


Xonsh-specific Aliases
=======================

``showcmd``
--------------------
Displays how commands and arguments are evaluated. Use ``-e`` to expand aliases.

.. code-block:: xonshcon

    @ showcmd echo The @('args') @(['list', 'is']) $(echo here) "and" --say="hello" to @([]) you
    ['echo', 'The', 'args', 'list', 'is', 'here', 'and', '--say="hello"', 'to', 'you']
    @ showcmd ls
    ls
    @ showcmd -e ls
    ['ls', '--group-directories-first', '-A', '--color']


``xonfig``
--------------------
Manages xonsh configuration information.

.. command-help:: xonsh.xonfig.xonfig_main

``xontrib``
--------------------
Manages xonsh extensions. More information is available at :doc:`xontrib`


``xcontext``
--------------------

.. code-block:: xonshcon

    @ xcontext
    [Current xonsh session]
    xpython: /home/snail/.local/xonsh-env/bin/python # Python 3.12.10
    xpip: /home/snail/.local/xonsh-env/bin/python -m pip

    [Current commands environment]
    xonsh: /home/snail/.local/xonsh-env/bin/xonsh
    python: /usr/bin/python # Python 3.11.6
    pip: /usr/bin/pip

    CONDA_DEFAULT_ENV: my-env

Report information about the current xonsh environment, including paths to the Python interpreter, pip, xonsh itself, and relevant environment variables.

By default, symlinks in the displayed paths are resolved to their real targets; pass ``--no-resolve`` (``-n``) to show the raw paths instead.


.. _aliases-xpip:

``xpip``
--------------------
Runs the ``pip`` package manager for xonsh itself. Useful for installations where xonsh is in an
isolated environment (e.g. conda, mamba, homebrew).

.. code-block:: xonshcon

    @ which pip
    /usr/bin/pip  # system pip
    @ which xpip
    /home/snail/.local/xonsh-env/bin/python -m pip  # current xonsh session pip
    @ xpip install fire
    @ import fire
    @ fire
    <module 'fire' from '/home/snail/.local/xonsh-env/lib/python3.11/site-packages/fire/__init__.py'>


``xpython``
--------------------

Alias to the Python interpreter that is currently running xonsh (``sys.executable``). This is useful for running Python modules or scripts in the same environment as the shell itself, especially in complex setups like AppImage.

.. code-block:: xonshcon

    @ python -V
    Python 3.12.10
    @ xpython -V
    Python 3.11.9
    @ which python
    /opt/homebrew/bin/python
    @ which xpython
    /home/snail/.local/xonsh-env/bin/python


.. _aliases-xxonsh:

``xxonsh``
--------------------

Launches exactly the same ``xonsh`` that was used to start the current session.

See :ref:`launch-xxonsh` for a worked example of using it as a building block to
launch ``tmux`` with this exact xonsh (the ``xtmux`` recipe).

Mnemonic: think of the initial ‘x’ as ‘c’—xxonsh stands for (c)urrent xonsh.

``xreset``
--------------------
Clean the xonsh context. All user variables will be deleted.

.. code-block:: xonshcon
    @ a=1
    @ a
    1
    @ xreset
    @ a
    Not found


``trace``
--------------------
Provides an interface to printing lines of source code prior to their execution.

.. command-help:: xonsh.tracer.tracermain


``exec`` and  ``xexec``
-------------------------

.. command-help:: xonsh.aliases.xexec


Command Decorators (Decorator Aliases)
======================================

``@error_raise`` and ``@error_ignore``
----------------------------------------
Use ``@error_raise`` to raise an exception if the command returns a non-zero exit code —
similar to ``$XONSH_SUBPROC_CMD_RAISE_ERROR`` but scoped to a single command, and it
raises unconditionally (even inside ``&&``/``||`` chains and even when
``$XONSH_SUBPROC_RAISE_ERROR`` is disabled).  Use ``@error_ignore`` to explicitly suppress
the raise — it also wins over the chain-result check performed by
``$XONSH_SUBPROC_RAISE_ERROR``.

.. code-block:: xonshcon

    @ r = !(@error_raise ls nonono)
    subprocess.CalledProcessError: Command '['@error_raise', 'ls', 'nonono']' returned non-zero exit status 1.

    @ r = !(@error_ignore ls nonono)

``@thread`` and ``@unthread``
-----------------------------
Use ``@thread`` and ``@unthread`` to run command as threadable or unthreadable e.g to have a result of SSH command:

.. code-block:: xonshcon

    @ !(@thread ssh host -T "echo 1")


``@path`` and ``@paths``
-----------------------------
Use ``@path`` and ``@paths`` to get Path object(s) from the command output.

.. code-block:: xonshcon

    @ dir = $(@path echo '/bin')
      dir.exists()
    @ dirs = $(@paths echo '/bin\n/etc')
      [p.exists() for p in dirs]


``@lines``
-----------
Return output as list of lines.

.. code-block:: xonshcon

    @ lines = $(@lines cat file)


``@json``
----------
Parses JSON and returns a JSON object.

.. code-block:: xonshcon

    @ data = $(@json curl https://example.com/data.json)


``@jsonl``
-----------
Parses JSON lines and returns a list of JSON objects.

.. code-block:: xonshcon

    @ items = $(@jsonl cat data.jsonl)


``@yaml``
----------
Parses YAML and returns a dict.

.. code-block:: xonshcon

    @ config = $(@yaml cat config.yaml)


Directory Stack
====================


``pushd``
--------------------
Adds a directory to the top of the directory stack, or rotates the stack,
making the new top of the stack the current working directory.

.. command-help:: xonsh.dirstack.pushd


``popd``
--------------------
Removes entries from the directory stack.

.. command-help:: xonsh.dirstack.popd


``dirs``
--------------------
Displays the list of currently remembered directories.  Can also be used to clear the
directory stack.

.. command-help:: xonsh.dirstack.dirs


Jobs
====================

``jobs``
--------------------
Display a list of all current jobs.


``fg``
--------------------
Bring the currently active job to the foreground, or, if a single number is
given as an argument, bring that job to the foreground.


``bg``
--------------------
Resume execution of the currently active job in the background, or, if a
single number is given as an argument, resume that job in the background.


``disown``
--------------------
The behavior of this command matches the behavior of zsh's disown
command which is as follows:

Remove the specified jobs from the job table; the shell will no longer
report their status, and will not complain if you try to exit an
interactive shell with them running or stopped. If no job is specified,
disown the current job.
If the jobs are currently stopped and the $AUTO_CONTINUE option is set
($AUTO_CONTINUE = True), a warning is printed containing information about
how to make them running after they have been disowned. If one of the
latter two forms is used, the jobs will automatically be made running,
independent of the setting of the $AUTO_CONTINUE option.



Source Aliases
====================


``source``
--------------------
Executes the contents of the provided files in the current context. This, of course,
only works on xonsh and Python files (``*.xsh``, ``*.py``). Use ``-e`` to ignore
extension.


``source-bash``
--------------------
Like the ``source`` command but for Bash files. This is a thin wrapper around
the ``source-foreign`` alias where the ``shell`` argument is automatically set
to ``bash``.


``source-zsh``
--------------------
Like the ``source`` command but for ZSH files. This is a thin wrapper around
the ``source-foreign`` alias where the ``shell`` argument is automatically set
to ``zsh``.


``source-foreign``
--------------------
Like the ``source`` command but for files in foreign (non-xonsh) languages.
It will pick up the environment and any aliases.

.. command-help:: xonsh.aliases.source_foreign


Windows Aliases
================

cmd-based Aliases
------------------
The following aliases on Windows are expanded to ``['cmd', '/c', alias]``:

.. code-block:: python

    {'cls': ['cmd', '/c', 'cls'],
     'copy': ['cmd', '/c', 'copy'],
     'del': ['cmd', '/c', 'del'],
     'dir': ['cmd', '/c', 'dir'],
     'erase': ['cmd', '/c', 'erase'],
     'md': ['cmd', '/c', 'md'],
     'mkdir': ['cmd', '/c', 'mkdir'],
     'mklink': ['cmd', '/c', 'mklink'],
     'move': ['cmd', '/c', 'move'],
     'rd': ['cmd', '/c', 'rd'],
     'ren': ['cmd', '/c', 'ren'],
     'rename': ['cmd', '/c', 'rename'],
     'rmdir': ['cmd', '/c', 'rmdir'],
     'time': ['cmd', '/c', 'time'],
     'type': ['cmd', '/c', 'type'],
     'vol': ['cmd', '/c', 'vol'],
     }



``activate``/``deactivate`` on Windows with Anaconda
------------------------------------------------------
On Windows with an Anaconda Python distribution, ``activate`` and
``deactivate`` are aliased to ``['source-cmd', 'activate.bat']`` and ``['source-cmd', 'deactivate.bat']``.
This makes it possible to use the same commands to activate/deactivate conda environments as
in cmd.exe.


``sudo`` on Windows
---------------------
On Windows, if no executables named ``sudo`` are found, Xonsh adds a ``sudo`` alias
that poly fills the "run as Admin" behavior with the help of ``ShellExecuteEx`` and
``ctypes``. It doesn't support any actual ``sudo`` parameters and just takes the
command to run.


Writing your own command decorator
==================================

A command decorator is a subclass of
:class:`xonsh.procs.specs.DecoratorAlias` registered under an
``@``-prefixed alias name. The base class exposes four hooks; you
override the ones you need:

* ``decorate_spec(spec)`` — runs once when the decorator is attached
  to a spec (parser-time-ish). Use to set spec attributes ahead of
  any execution. ``SpecAttrDecoratorAlias`` (used by ``@thread``,
  ``@lines``, ``@json``, …) is a thin wrapper that just sets a dict
  of attributes here.
* ``decorate_spec_pre_run(pipeline, spec, spec_num)`` — runs once
  per spec immediately before that spec's subprocess is spawned.
* ``on_command_pipeline_pre_run(cp)`` — runs once for the entire
  pipeline before any subprocess is spawned. Receives the
  not-yet-run :class:`xonsh.procs.pipelines.CommandPipeline`.
* ``on_command_pipeline_post_run(cp)`` — runs once for the entire
  pipeline at the same point as the
  :func:`xonsh.events.on_post_command_pipeline` event, with
  ``cp.returncode`` and other completion fields populated.

The ``@`` prefix in the alias name is just a convention — the parser
treats anything registered as a ``DecoratorAlias`` instance as a
decorator regardless of name, but the prefix keeps decorators visually
distinct from regular aliases.

The example below registers ``@trace``, which prints the resolved
pipeline (with ``|`` separators), the return code, and the elapsed
time — using the two pipeline-level hooks. ``print`` writes to
``sys.stderr`` so the trace appears in the right order even when the
inner command is buffered.

.. code-block:: python

    # ~/.xonshrc
    @aliases.register("@trace")
    class TraceCmd(@.imp.xonsh.procs.specs.DecoratorAlias):
        """Print the resolved pipeline before and after execution."""

        descr = "Command decorator. Trace the pipeline (cmd, rtn, elapsed time)."

        @staticmethod
        def _fmt_pipeline(cp):
            return " | ".join(" ".join(spec.cmd) for spec in cp.specs)

        def on_command_pipeline_pre_run(self, cp):
            print(f"[trace] >>> {self._fmt_pipeline(cp)}",
                  file=@.imp.sys.stderr, flush=True)
            cp._trace_t0 = @.imp.time.monotonic()

        def on_command_pipeline_post_run(self, cp):
            dt = @.imp.time.monotonic() - getattr(cp, "_trace_t0", @.imp.time.monotonic())
            print(
                f"[trace] <<< {self._fmt_pipeline(cp)}  "
                f"rtn={cp.returncode}  ({dt * 1000:.1f} ms)",
                file=@.imp.sys.stderr, flush=True,
            )

``@aliases.register`` accepts a ``DecoratorAlias`` subclass and
auto-instantiates it under the given name (here ``@trace``). The bare
form (``@aliases.register`` without args) derives the name from the
class's ``__name__`` — only useful when you happen to name the class
exactly the way you want the alias spelled.

Usage:

.. code-block:: xonshcon

    @ @trace echo hello world
    [trace] >>> echo hello world
    hello world
    [trace] <<< echo hello world  rtn=0  (6.1 ms)

    @ @trace ls /etc/hosts | wc -l
    [trace] >>> ls -G /etc/hosts | wc -l
    1
    [trace] <<< ls -G /etc/hosts | wc -l  rtn=0  (15.7 ms)

A few details that surface in the example above:

* ``spec.cmd`` is the *resolved* argv after alias expansion, so ``ls``
  shows up as ``ls -G`` (or whatever your shell aliases it to).
* Storing ``_trace_t0`` directly on the pipeline avoids a global
  ``id(cp)``-keyed dict to bridge the two hooks.
* The hooks fire once per pipeline, not once per spec — a pipeline
  like ``cmd1 | cmd2`` produces a single ``>>> ... | ...`` /
  ``<<< ... | ...`` pair.


See also
========

* :doc:`callable_aliases` -- writing callable aliases in depth
* :doc:`subprocess` -- subprocess operators and capturing modes
* :doc:`xonshrc` -- defining aliases in RC files
