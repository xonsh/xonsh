==============================
Updating and customizing xonsh
==============================

Updating xonsh
==============

How to update xonsh depend on the install method.

**xonsh installed via pip**

If you have installed via pip (possibly into a virtual environment),
then you can update xonsh from within itself with the following
command:

.. code-block:: console

   @ xpip install --upgrade xonsh

``xpip`` (note the "x" at the  beginning of ``xpip``) is a predefined alias pointing to the ``pip`` command associated with the Python executable running this xonsh.

**xonsh installed via a package manager**

If you have installed via a package manager, it is recommended to update xonsh through the  package manager's appropriate command. For example, on macOS if you have installed via homebrew, you should update like this:

.. code-block:: console

   $ brew upgrade xonsh

Customizing xonsh - How do I...
===============================

.. _change_theme:

...change the current color theme?
----------------------------------

You can view the available styles by typing

.. code-block:: console

   @ xonfig styles

For a quick peek at the theme's colors you can do

.. code-block:: console

   @ xonfig colors <theme name>

To set a new theme, do

.. code-block:: console

   @ $XONSH_COLOR_STYLE='<theme name>'

Registering custom styles
^^^^^^^^^^^^^^^^^^^^^^^^^

If you aren't happy with the styles provided by us (and ``pygments``), you can create and register custom styles.

To do so, add something similar to your ``.xonshrc``:

.. code-block:: python

   from xonsh.tools import register_custom_style
   mystyle = {
       "Literal.String.Single": "#ff88aa",
       "Literal.String.Double": "#ff4488",
       "RED": "#008800",
   }
   register_custom_style("mystyle", mystyle, base="monokai")
   $XONSH_COLOR_STYLE="mystyle"

You can check ``xonfig colors`` for the token names. The ``base`` style will be used as a fallback for styles you don't set - pick one from ``xonfig styles`` (``default`` is used if omitted).

.. _import_local_modules:

...import python modules from a local directory?
------------------------------------------------

The modules available for import in a given ``xonsh`` session depend on what's
available in ``sys.path``. If you want to be able to import a module that
resides in the current directory, ensure that there is an empty string as the
first element of your ``sys.path``

.. code-block:: console

   @ import sys
   @ sys.path.insert(0, '')

.. _default_shell:

...set ``xonsh`` as my default shell?
-------------------------------------

If you want to use xonsh as your default shell, you will first have
to add xonsh to ``/etc/shells``.

First ensure that xonsh is on your ``$PATH``

.. code-block:: console

    $ which xonsh

Then, as root, add xonsh to the shell list

.. code-block:: console

   # which xonsh >> /etc/shells

To change shells, run

.. code-block:: console

   $ chsh -s $(which xonsh)

You will have to log out and log back in before the changes take effect.

.. _select_completion_result:

...select a tab completion result without executing the current line?
---------------------------------------------------------------------

In the ``prompt_toolkit`` shell, you can cycle through possible tab-completion
results using the TAB key and use ENTER to select the completion you want. By
default, ENTER will also execute the current line. If you would prefer to not
automatically execute the line (say, if you're constructing a long pathname),
you can set

.. code-block:: xonshcon

   $COMPLETIONS_CONFIRM=True

in your ``xonshrc``

.. _add_args_builtin_alias:

...add a default argument to a builtin ``xonsh`` alias?
-------------------------------------------------------

If you want to add a default argument to a builtin alias like ``dirs`` the
standard alias definition method will fail. In order to handle this case you can
use the following solution in your ``xonshrc``:

.. code-block:: python

   from xonsh.dirstack import dirs

   def _verbose_dirs(args, stdin=None):
       return dirs(['-v'] + args, stdin=stdin)

   aliases['dirs'] = _verbose_dirs


.. _terminal_tabs:

...make terminal tabs start in the correct directory?
-----------------------------------------------------

If you use Gnome Terminal or another VTE terminal and it doesn't start new tabs
in the CWD of the original TAB, this is because of a custom VTE interface. To
fix this, please add ``{vte_new_tab_cwd}`` somewhere to you prompt:

.. code-block:: xonsh

    $PROMPT = '{vte_new_tab_cwd}' + $PROMPT

This will issue the proper escape sequence to the terminal without otherwise
affecting the displayed prompt.

.. _open_terminal_here:

...set up the "Open Terminal Here" action in Thunar?
----------------------------------------------------

If you use Thunar and "Open Terminal Here" action does not work,
you can try to replace a command for this action by the following:

.. code-block:: sh

    exo-open --working-directory %f --launch TerminalEmulator xonsh --shell-type=best

In order to do this, go to ``Edit > Configure custom actions...``,
then choose ``Open Terminal Here`` and click on ``Edit currently selected action`` button.

.. _unicode_troubles:

...use utf-8 characters in xonsh?
---------------------------------

If you are unable to use utf-8 (ie. non-ascii) characters in xonsh. For example if you get the following output

.. code-block:: console

    @ echo "ßðđ"
    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    UnicodeEncodeError: 'ascii' codec can't encode characters in position 0-2: ordinal not in range(128)

The problem might be:

- Your locale is not set to utf-8, to check this you can set the content of the
  environment variable ``LC_TYPE``
- Your locale is correctly set but **after** xonsh started. This is typically
  the case if you set your ``LC_TYPE`` inside your `xonshrc <xonshrc.rst>`_ and xonsh is
  your default/login shell. To fix this you should see the documentation of your
  operating system to know how to correctly setup environment variables before
  the shell start (``~/.pam_environment`` for example)

.. _fix_libgcc_core_dump:

...fix a ``libgcc_s.so.1`` error?
---------------------------------

On certain flavors of Linux you may periodically encounter this error message
when starting ``xonsh``:

.. code-block:: xonshcon

   libgcc_s.so.1 must be installed for pthread_cancel to work
   Aborted (core dumped)

This is due to an upstream Python problem and can be fixed by setting
``LD_PRELOAD``:

.. code-block:: bash

   $ env LD_PRELOAD=libgcc_s.so.1 xonsh

...color my man pages?
----------------------
You can add add `man page color support`_ using ``less`` environment
variables:

.. code-block:: xonsh

    # Coloured man page support
    # using 'less' env vars (format is '\E[<brightness>;<colour>m')
    $LESS_TERMCAP_mb = "\033[01;31m"     # begin blinking
    $LESS_TERMCAP_md = "\033[01;31m"     # begin bold
    $LESS_TERMCAP_me = "\033[0m"         # end mode
    $LESS_TERMCAP_so = "\033[01;44;36m"  # begin standout-mode (bottom of screen)
    $LESS_TERMCAP_se = "\033[0m"         # end standout-mode
    $LESS_TERMCAP_us = "\033[00;36m"     # begin underline
    $LESS_TERMCAP_ue = "\033[0m"         # end underline

.. _man page color support:
    https://wiki.archlinux.org/index.php/Color_output_in_console#less

.. _xonsh_inside_emacs:

...use xonsh inside Emacs?
----------------------------------

see `emacs <editors.html>`_.

See also
========

 * `Q&A in the xonsh repository <https://github.com/xonsh/xonsh/discussions>`_
