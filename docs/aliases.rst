.. _aliases:

********************
Built-in Aliases
********************
This page describes the xonsh built-in commands and aliases.

``cd``
===================
Changes the directory. If no directory is specified (i.e. if there are no arguments)
then this changes to the current user's home directory.


``pushd``
===================
Adds a directory to the top of the directory stack, or rotates the stack,
making the new top of the stack the current working directory.

.. command-help:: xonsh.dirstack.pushd


``popd``
===================
Removes entries from the directory stack.

.. command-help:: xonsh.dirstack.popd


``dirs``
===================
Displays the list of currently remembered directories.  Can also be used to clear the
directory stack.

.. command-help:: xonsh.dirstack.dirs


``jobs``
===================
Display a list of all current jobs.


``fg``
===================
Bring the currently active job to the foreground, or, if a single number is
given as an argument, bring that job to the foreground.


``bg``
====================
Resume execution of the currently active job in the background, or, if a
single number is given as an argument, resume that job in the background.


``EOF``, ``exit``, and ``quit``
===================================
The commands ``EOF``, ``exit``, and ``quit`` all alias the same action, which is to
leave xonsh in a safe manner. Typing ``Crtl-d`` is the same as typing ``EOF`` and
pressing enter.


``xexec``
====================
xexec uses the ``os.execvpe()`` function to replace the xonsh process with
the specified program. This provides the functionality of the bash ``exec``
builtin.

.. code-block:: bash

  >>> xexec bash
  bash $


``source``
====================
Executes the contents of the provided files in the current context. This, of course,
only works on xonsh and Python files.


``source-bash``
====================
Like the ``source`` command but for Bash files. This is a thin wrapper around
the ``source-foreign`` alias where the ``shell`` argument is autoamtically set
to ``bash``.


``source-foreign``
====================
Like the ``source`` command but for files in foreign (non-xonsh) languages.
It will pick up the environment and any aliases.

.. command-help:: xonsh.aliases.source_foreign


``history``
====================
Tools for dealing with xonsh history. See `the history tutorial <tutorial_hist.html>`_
for more information all the history command and all of its sub-commands.

.. command-help:: xonsh.history.history_main


``replay``
=====================
Replays a xonsh history file.  See `the replay section of the history tutorial
<tutorial_hist.html#replay-action>`_ for more information about this command.

.. command-help:: xonsh.replay.replay_main


``!n``
====================
Re-runs the nth command as specified in the argument.

.. command-help:: xonsh.aliases.bang_n


``!!``
==============
Re-runs the last command. Just a wrapper around ``!n``.


``timeit``
===============
Runs timing study on arguments. Similar to IPython's ``%timeit`` magic.


``scp-resume``
=================
Simple alias defined as ``['rsync', '--partial', '-h', '--progress', '--rsh=ssh']``.

``showcmd``
============
Displays how comands and arguments are evaluated.


``ipynb``
=================
Simple alias defined as ``['ipython', 'notebook', '--no-browser']``.


``trace``
=================
Provides an interface to printing lines of source code prior to their execution.

.. command-help:: xonsh.tracer.tracermain


``xonfig``
=================
Manages xonsh configuration information.

.. command-help:: xonsh.xonfig.xonfig_main


Windows cmd Aliases
=======================
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
=========================================================
On Windows with an Anaconda Python distribution, ``activate`` and
``deactivate`` are aliased to ``['source-bat activate']`` and ``['source-bat deactivate']``.
This makes it possible to use the same commands to activate/deactivate conda environments as
in cmd.exe.


``sudo`` on Windows
====================
On Windows, if no executables named ``sudo`` are found, Xonsh adds a ``sudo`` alias
that poly fills the "run as Admin" behavior with the help of ``ShellExecuteEx`` and
``ctypes``. It doesn't support any actual ``sudo`` parameters and just takes the
command to run.


``ls``
====================
The ``ls`` command is aliased to ``['ls', '--color=auto', '-v']`` normally.  On Mac OSX
it is instead aliased to ``['ls', '-G']``.


``grep``
====================
The ``grep`` command is aliased to ``['grep', '--color=auto']``.


``xontrib``
==============
Manages xonsh extensions.
