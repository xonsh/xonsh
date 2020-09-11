
==============================
Editor Support
==============================

.. contents::
   :local:

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
in the shell, but you loose xonsh's completion feature.

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

Emacs will prompt you for the path of the xonsh exeutable when you
start up ``ansi-term``.
