==========================
OSX Guide
==========================

Installation
============

You can install xonsh using homebrew, conda, pip, or from source.

**homebrew:**

.. code-block:: bash

   $ brew install xonsh


**conda:**

.. code-block:: bash

    $ conda config --add channels conda-forge
    $ conda install xonsh

.. note:: For the bleeding edge development version use ``conda install -c xonsh/channel/dev xonsh``
    

**pip:**

.. code-block:: bash

    $ pip3 install xonsh


**source:** Download the source `from github <https://github.com/xonsh/xonsh>`_
(`zip file <https://github.com/xonsh/xonsh/archive/master.zip>`_), then run
the following from the source directory,

.. code-block:: bash

    $ python3 setup.py install


Extras for OSX
==============

On Mac OSX, it is *strongly* recommended to install the ``gnureadline`` library if using the readline shell.  ``gnureadline`` can be installed via pip:

.. code-block:: bash

    $ pip3 install gnureadline

Xonsh has support for using bash completion files on the shell, to use it you need to install the bash-completion package

.. code-block:: bash

    $ brew install bash-completion



.. include:: add_to_shell.rst

.. include:: dependencies.rst
