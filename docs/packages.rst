Package Manager
===============

You can install xonsh using ``conda``, ``pip`` or the package manager for
your operating system distribution.

For the fullest interactive user experience, these additional packages should also be installed:

  :prompt-toolkit: for command completion, configurable key bindings and especially multi-line line editing.
  :pygments: for xonsh and Python syntax-specific highlighting
  :setproctitle: updates process title (in terminal window and process monitor) to match Xonsh arguments.

Installing with these packages is the recommended configuration and is documented first.
If you are operating in a specialized or restricted environment, you can install just the xonsh package, as
described in `fewer prerequisites`_


**conda:**

.. code-block:: console

    $ conda config --add channels conda-forge
    $ conda install xonsh


**pip:** Typically you will activate a virtual environment and install xonsh there.  This will ensure that you invoke the
correct Python interpreter and ``pip`` module.

.. code-block:: console

    $ pip install 'xonsh[full]'

This uses the pip 'extras' syntax, and is equivalent to:

.. code-block:: console

    $ pip install pygments prompt-toolkit setproctitle xonsh

The above ``pip`` commands may have to be spelled ``pip3`` or ``sudo pip3`` if you are not installing in a virtual environment.

**source:** Pip can also install the most recent xonsh source code from the
`xonsh project repository <https://github.com/xonsh/xonsh>`_.

.. code-block:: console

    $ pip install pygments prompt-toolkit setproctitle https://github.com/xonsh/xonsh/archive/main.zip

Spelling of ``pip`` command may likewise have to be amended as noted above.

**core shell:** When using ``xonsh`` as a default shell (and we do!), it's important to ensure that it is installed in a
Python environment that is independent of changes from the system package manager.  If you are installing
``xonsh`` via your system package-manager, this is handled for you.  If you install ``xonsh`` outside of your
system package manager, you can use `xonsh-install <https://github.com/anki-code/xonsh-install>`_ for this.

**platform package managers**
Various operating system distributions have platform-specific package managers which may offer a xonsh package.
This may not be  the most current version of xonsh, but it should have been tested for stability on that platform
by the distribution managers.


   +---------------------------+-----------------------------+---------------------+
   | OS or distribution        |  command                    |   Package(s)        |
   +===========================+=============================+=====================+
   | Debian/Ubuntu             | ``$ [sudo] apt install``    |                     |
   +---------------------------+-----------------------------+    pygments         |
   | Fedora                    | ``$ [sudo] dnf install``    |    prompt-toolkit   |
   +---------------------------+-----------------------------+    setproctitle     |
   | Arch Linux                | ``$ [sudo] pacman -S``      |    xonsh            |
   +---------------------------+-----------------------------+                     |
   | OSX                       | ``$ [sudo] brew install``   |                     |
   +---------------------------+-----------------------------+---------------------+


If you run into any problems, please let us know!

Fewer Prerequisites
--------------------

A design goal of Xonsh is to run in any environment that supports a (supported) Python interpreter, you
can install just the ``xonsh`` package (using any package manager).

.. code-block:: console

    pip install xonsh

When it starts up, if xonsh does not find ``pygments`` or ``setproctitle`` packages, it simply does not colorize
or highlight syntax or set process title, respectively.

If it does not find ``prompt-toolkit`` package, it will
use the Python ``readline`` module (which reads configuration  file ``.inputrc`` in a manner compatible with ``GNU readline``).
To ensure xonsh uses ``readline`` even if ``prompt-toolkit`` is installed, configure this in your
`xonshrc <xonshrc.rst>`_ (e.g. ``~/.xonshrc``) file:

.. code-block:: xonshcon

    $SHELL_TYPE = 'readline'

Windows
-------

On Windows 10, the separately-installable `Windows Terminal app`_ is recommended.

.. _`Windows Terminal app`: platform-issues.html#windows-terminal
