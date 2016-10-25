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

.. code-block:: python

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
