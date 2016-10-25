=====================
Customizing ``xonsh``
=====================

.. contents::
   :local:

How do I...
===========

.. _change_theme:

...change the current color theme?
----------------------------------

You can view the available styles by typing

.. code-block:: console

   $ xonfig styles

For a quick peek at the theme's colors you can do

.. code-block:: console

   $ xonfig colors <theme name>

To set a new theme, do

.. code-block:: console

   $ $XONSH_COLOR_STYLE='<theme name>'

.. _import_local_modules:

...import python modules from a local directory?
------------------------------------------------

The modules available for import in a given ``xonsh`` session depend on what's
available in ``sys.path``. If you want to be able to import a module that
resides in the current directory, ensure that there is an empty string as the
first element of your ``sys.path``

.. code-block:: xonshcon

   $ import sys
   $ sys.path.insert(0, '')

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

.. code-block:: xonsh

    echo "ßðđ"
    
    xonsh: For full traceback set: $XONSH_SHOW_TRACEBACK = True
    UnicodeEncodeError: 'ascii' codec can't encode characters in position 0-2: ordinal not in range(128)
    
The problem might be: 

- Your locale is not set to utf-8, to check this you can set the content of the
  environment variable ``LC_TYPE``
- Your locale is correctly set but **after** xonsh started. This is typically
  the case if you set your ``LC_TYPE`` inside your ``.xonshrc`` and xonsh is
  your default/login shell. To fix this you should see the documentation of your
  operating system to know how to correctly setup environment variables before
  the shell start (``~/.pam_environment`` for example)
