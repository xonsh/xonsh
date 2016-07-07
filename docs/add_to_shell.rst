Additional Setup
================
If you want to use xonsh as your default shell, you will first have
to add xonsh to `/etc/shells`.

First ensure that xonsh is on your ``$PATH``

.. code-block:: bash

    $ which xonsh

Then, as root, add xonsh to the shell list

.. code-block:: bash

   # which xonsh >> /etc/shells

To change shells, run

.. code-block:: bash

   $ chsh -s $(which xonsh)

You will have to log out and log back in before the changes take effect.
