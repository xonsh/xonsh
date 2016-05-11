==========================
Linux Guide
==========================

Installation
============

You can install xonsh using ``conda``, ``pip``, or from source.

**conda:**

.. code-block:: bash

    $ conda install -c conda-forge xonsh

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
``yaourt``, ``aura``, ``pacaur``, ``PKGBUILD``, etc...:

**yaourt:**

.. code-block:: bash

    $ yaourt -Sa xonsh      # yaourt will call sudo when needed

**aura:**

.. code-block:: bash

    $ sudo aura -A xonsh

**pacaur:**

.. code-block:: bash

    $ pacaur -S xonsh

If you run into any problems, please let us know!

.. include:: add_to_shell.rst

.. include:: dependencies.rst
