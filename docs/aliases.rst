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

``popd``
===================
Removes entries from the directory stack.

``dirs``
===================
Displays the list of currently remembered directories.  Can also be used to clear the 
directory stack.

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
the ``source-foreign`` alias.

``source-foreign``
====================
Like the ``source`` command but for files in foreign (non-xonsh) languages. 
It will pick up the environment and any aliases.

``history``
====================
Tools for dealing with xonsh history. See `the history tutorial <tutorial_hist.html>`_
for more information all the history command and all of its sub-commands.

``replay``
=====================
Replays a xonsh history file.  See `the replay section of the history tutorial 
<tutorial_hist.html#replay-action>`_ for more information about this command.

``!n``
====================
Re-runs the nth command as specified in the argument.

``!!``
==============
Re-runs the last command. Just a wrapper around ``!n``.

``timeit``
===============
Runs timing study on arguments. Similar to IPython's ``%timeit`` magic.

``scp-resume``
=================
Simple alias defined as ``['rsync', '--partial', '-h', '--progress', '--rsh=ssh']``.

``ipynb``
=================
Simple alias defined as ``['ipython', 'notebook', '--no-browser']``.


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

``which`` on Windows
=====================
On Windows, ``which`` is aliased to ``['where']``.


``ls``
====================
The ``ls`` command is aliased to ``['ls', '--color=auto', '-v']`` normally.  On Mac OSX
it is instead aliased to ``['ls', '-G']``.


``grep``
====================
The ``grep`` command is aliased to ``['grep', '--color=auto']``.

