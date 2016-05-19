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



Possible conflicts with Bash
============================

Depending on how your installation of Bash is configured, Xonsh may have trouble
loading certain shell modules. Particularly if you see errors similar to this
when launching Xonsh:

.. code-block:: bash

    bash: module: line 1: syntax error: unexpected end of file
    bash: error importing function definition for `BASH_FUNC_module'
    bash: scl: line 1: syntax error: unexpected end of file
    bash: error importing function definition for `BASH_FUNC_scl'
    bash: module: line 1: syntax error: unexpected end of file
    bash: error importing function definition for `BASH_FUNC_module'
    bash: scl: line 1: syntax error: unexpected end of file
    bash: error importing function definition for `BASH_FUNC_scl'

...You can correct the problem by unsetting the modules, by adding the following
lines to your ``~/.bashrc file``:

.. code-block:: bash

    unset module
    unset scl
