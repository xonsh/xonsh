==========================
Linux Guide
==========================

Installation
============

You can install xonsh using conda, pip, or from source.

**conda:**

.. code-block:: bash

    $ conda install -c xonsh xonsh

.. note:: For the bleeding edge development version use ``conda install -c xonsh/channel/dev xonsh``
    

**pip:**

.. code-block:: bash

    $ pip install xonsh


**source:** Download the source `from github <https://github.com/scopatz/xonsh>`_
(`zip file <https://github.com/scopatz/xonsh/archive/master.zip>`_), then run
the following from the source directory,

.. code-block:: bash

    $ python setup.py install


Arch Linux users can install xonsh from the Arch User Repository with e.g.
yaourt or aura:

**yaourt:**

.. code-block:: bash

    $ yaourt -Sa xonsh      # yaourt will call sudo when needed

**aura:**

.. code-block:: bash

    $ sudo aura -A xonsh

If you run into any problems, please let us know!

Configuration
================

If you want to use xonsh as your default shell, you will first have to add xonsh to `/etc/shells`.

First ensure that xonsh is on your $PATH

.. code-block:: bash

    $ which xonsh

Then, as root, add xonsh to the shell list

.. code-block:: bash

   # echo $(which xonsh) >> /etc/shells

To change shells, run

.. code-block:: bash

   $ chsh -s $(which xonsh)

You will have to log out and log back in before the changes take effect.   
