Typical Interactive Installation
================================

For the full Xonsh experience, with colorized syntax and multi-line command editing, you must 
explicitly install the prerequisite packages before installing xonsh.  
Xonsh will check for these packages at startup and use 
them if present, but the installation of Xonsh in any package manager will not automatically install them.

You can install xonsh using ``conda``, ``pip``, or from source.  

**conda:**

.. code-block:: console

    $ conda config --add channels conda-forge
    # For prerequisites
    $ conda install pygments prompt-toolkit setproctitle
    $ conda install xonsh


**pip:** Typically you will activate a virtual environment and install xonsh there.  This will ensure that you invoke the 
correct python interpreter and ``pip`` module. 

.. code-block:: console

    # For prerequisites
    $ pip install pygments prompt-toolkit setproctitle
    $ pip install xonsh

The above ``pip`` command may have to be spelled ``pip3`` or ``sudo pip3`` if you are not installing in a virtual environment.

**source:** The most recent xonsh source code from the 
`xonsh project repository <https://github.com/xonsh/xonsh>`_.

.. code-block:: console

    # For prerequisites
    $ pip install pygments prompt-toolkit setproctitle
    $ pip install https://github.com/xonsh/xonsh/archive/master.zip

Spelling of ``pip`` command in this example may have to be amended as noted above.

**platform package managers**
Various operating system distributions have platform-specific package managers which may offer a xonsh package.  
This may not be  the most current version of xonsh, but it should have been tested for stability on that platform
by the distribution managers.


+--------------+-----------------+----------------------------------+
| OS or        |  command        |   Prerequesite package(s)        |
+--------------+-----------------+----------------------------------+
| distribution |                 |     Xonsh package                |
+==============+=================+==================================+
| Debian/Ubuntu | ``$ [sudo] apt install`` | :Prerequisites:        |
+--------------+---------------------------+    pygments            |
| Fedora       |  ``$ [sudo] dnf install``  |   prompt-toolkit      |
+--------------+----------------------------+   setproctitle        |
| Arch Linux   | ``$ [sudo] pacman -S``     |                       |
+--------------+----------------------------+  :Xonsh:              |
| OSX          |  ``$ [sudo] brew install`` |    xonsh              |  
+--------------+-----------------+----------------------------------+


If you run into any problems, please let us know!

.. include:: dependencies.rst

Fewer Prerequisites
-------------------------

A design goal of Xonsh is to run in any environment that supports a (supported) Python interpreter, so you do not 
have to install any of the optional prerequisites.

When it starts up, if xonsh does not find ``pygments`` or ``setproctitle`` packages, it simply does not colorize 
or highlight syntax or set process title, respectively.  

If it does not find ``prompt-toolkit`` package, it will 
use the Python ``readline`` module (which reads configuration  file ``.inputrc`` in a manner compatible with ``GNU readline``).


Customization
-------------

See the `xonsh customization guide <customization.html>`_ for more details on setting up ``xonsh``!


