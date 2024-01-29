
======================
Editor and IDE Support
======================

Sublime Text
============
There is a `xonsh package`_ for **Sublime Text 4** (build > 4075). To install:

- Via **Package Control**: open (``^``/``⌘`` ``⇧`` ``P``) ``Command Palette`` → ``Package Control: Install Package`` → ``xonsh``
- **Manually**: clone the repository to your `Sublime Text packages`_ directory and rename it to ``xonsh``

  .. code-block:: sh

    cd /path/to/sublime/packages/directory
    git clone https://github.com/eugenesvk/sublime-xonsh.git
    mv sublime-xonsh xonsh

.. _xonsh package: https://packagecontrol.io/packages/xonsh
.. _Sublime Text packages: https://www.sublimetext.com/docs/packages.html


Visual Studio Code (VS Code)
============================
There is `xonsh extension for VS Code`_. To install search "xonsh" using extensions
menu or just press ``F1`` and run without `>` preceding:

.. code-block::

    ext install jnoortheen.xonsh

.. https://github.com/microsoft/vscode/issues/200374

Since version 1.86 of VS Code, the editor also supports loading the environment for users with xonsh as their default shell.

.. _xonsh extension for VS Code: https://marketplace.visualstudio.com/items?itemName=jnoortheen.xonsh


Emacs
=====

Emacs Xonsh mode
----------------

There is an emacs mode for editing xonsh scripts available from the
`MELPA repository`_. If you are not familiar see the installation
instructions there.

Then just add this line to your emacs configuration file:

.. code-block:: emacs-lisp

    (require 'xonsh-mode)


.. _MELPA repository: https://melpa.org/#/xonsh-mode


Xonsh Comint buffer
-------------------

You can use xonsh as your `interactive shell in Emacs
<https://www.gnu.org/software/emacs/manual/html_node/emacs/Interactive-Shell.html>`_
in a Comint buffer. This way you keep all the Emacs editing power
in the shell, but you lose xonsh's completion feature.

Make sure you install xonsh with readline support and in your
``.xonshrc`` file define

.. code-block:: xonsh

    $SHELL_TYPE = 'readline'

Also, in Emacs set ``explicit-shell-file-name`` to your xonsh executable.

Xonsh Ansi-term buffer
----------------------

The second option is to run xonsh in an Ansi-term buffer inside
Emacs. This way you have to switch modes if you want do Emacs-style
editing, but you keep xonsh's impressive completion.

For this it is preferred to have xonsh installed with the
prompt-toolkit. Then you can leave ``$SHELL_TYPE`` at its default.

Emacs will prompt you for the path of the xonsh executable when you
start up ``ansi-term``.

Vim
===

There is `xonsh syntax file for vim`_. To install run:

.. code-block::

    git clone --depth 1 https://github.com/linkinpark342/xonsh-vim ~/.vim

.. _xonsh syntax file for vim: https://github.com/linkinpark342/xonsh-vim
