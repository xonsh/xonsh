==========================
OSX Guide
==========================

Installation
============

You can install xonsh using conda, pip, or from source.

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

    $ pip install .


.. include:: add_to_shell.rst

.. include:: dependencies.rst


GNU Readline
============

On Mac OSX, it is *strongly* recommended to install the ``gnureadline`` library if using the readline shell.  ``gnureadline`` can be installed via pip:

.. code-block:: bash

    $ pip install gnureadline
