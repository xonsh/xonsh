==========================
OSX Guide
==========================

Installation
============

You can install xonsh using homebrew, conda, pip, or from source.

**homebrew:**

.. code-block:: console

   $ brew install xonsh


**conda:**

.. code-block:: console

    $ conda config --add channels conda-forge
    $ conda install xonsh
    

**pip:**

.. code-block:: console

    $ pip3 install xonsh


**source:** Download the source `from github <https://github.com/xonsh/xonsh>`_
(`zip file <https://github.com/xonsh/xonsh/archive/master.zip>`_), then run
the following from the source directory,

.. code-block:: console

    $ python3 setup.py install


Extras for OSX
==============

On Mac OSX, it is *strongly* recommended to install the ``gnureadline`` library if using the readline shell.  ``gnureadline`` can be installed via pip:

.. code-block:: console

    $ pip3 install gnureadline

Xonsh has support for using bash completion files on the shell, to use it you need to install the bash-completion package. The regular bash-completion package uses v1 which mostly works, but `occasionally has rough edges <https://github.com/xonsh/xonsh/issues/2111>`_ so we recommend using bash-completion v2 which is installed using the bash-completion2 package.

.. code-block:: console

    $ brew install bash-completion2

.. include:: dependencies.rst

Customization
=============

See the `xonsh customization guide <customization.html>`_ for more details on setting up ``xonsh``!
