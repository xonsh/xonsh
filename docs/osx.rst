==========================
OSX Guide
==========================

Installation
============

You can install xonsh using a package manager including homebrew, macports, conda, pip, or from source.

**homebrew:**

.. code-block:: console

   $ brew install xonsh


**MacPorts:**

.. code-block:: console

   $ sudo port install xonsh

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

Extras for macOS
==================
readline
--------

On macOS, it is *strongly* recommended to install the ``gnureadline`` library if using the readline shell.  ``gnureadline`` can be installed via pip:

.. code-block:: console

    $ pip3 install gnureadline

Path Helper
-----------

macOS provides a `path helper
<http://www.softec.lu/site/DevelopersCorner/MasteringThePathHelper>`_,
which by default configures paths in bash and other POSIX or C  shells. Without
including these paths, common tools including those installed by Homebrew
may be unavailable. See ``/etc/profile`` for details on how it is done.
To ensure the path helper is invoked on xonsh (for all users), add the
following to ``/etc/xonshrc``::

    source-bash $(/usr/libexec/path_helper -s)

To incorporate the whole functionality of ``/etc/profile``::

    source-bash --seterrprevcmd "" /etc/profile



Tab completion
--------------
Xonsh has support for using bash completion files on the shell, to use it you need to install the bash-completion package. The regular bash-completion package uses v1 which mostly works, but `occasionally has rough edges <https://github.com/xonsh/xonsh/issues/2111>`_ so we recommend using bash-completion v2.

Bash completion comes from <https://github.com/scop/bash-completion> which suggests you use a package manager to install it, this manager will also install a new version of bash without affecting  /bin/bash. Xonsh also needs to be told where the bash shell file that builds the completions is, this has to be added to $BASH_COMPLETIONS. The package includes completions for many Unix commands.

Common packaging systems for MacOs include

 -  Homebrew where the bash-completion2 package needs to be installed.

    .. code-block:: console

       $ brew install bash-completion2
       
    This will install the bash_completion file in `/usr/local/share/bash-completion/bash_completion` which is in the current xonsh code and so should just work.

 - `MacPorts <https://trac.macports.org/wiki/howto/bash-completion>`_ where the bash-completion port needs to be installed.

   .. code-block:: console

    $ sudo port install bash-completion
     


   This includes a bash_completion file that needs to be added to the environment.

   .. code-block:: console

    $ $BASH_COMPLETIONS.insert(0, '/opt/local/share/bash-completion/bash_completion')

Note that the `bash completion project page <https://github.com/scop/bash-completion>`_ gives the script to be called as in .../profile.d/bash_completion.sh which will the call the script mentioned above and one in $XDG_CONFIG_HOME . Currently xonsh seems only to be able to read the first script directly.


.. include:: dependencies.rst

Customization
=============

See the `xonsh customization guide <customization.html>`_ for more details on setting up ``xonsh``!
