*******************
Mamba Install Xonsh
*******************

Xonsh is a Python-based shell, and running xonsh requires Python to be installed.
The Python version and its packages can be installed in various locations. When
you execute ``import`` or any other Python code during a xonsh session, it is
executed in the Python environment that was used to start the current xonsh
instance.

When xonsh is used as a core shell, it is necessary to keep the Python environment
with xonsh stable, predictable, and independent of system changes. Lightweight
environment managers such as ``venv``, ``pipx``, or ``rye`` do not fully address
this requirement. Package managers that can install fully isolated Python
environments as a core feature, such as ``miniconda`` or ``micromamba``, should
be used.

The ``mamba-install-xonsh.sh`` script creates an independent Python environment
for xonsh using `mamba <https://mamba.readthedocs.io/>`_ in ``$TARGET_DIR`` without
affecting any other components of the system. This is an isolated,
xonsh-specific environment that is not affected by system package upgrades,
Python version changes, or other experiments with environments. You can use
``xpip`` and ``xmamba`` to intentionally install packages into this environment.

Install the latest xonsh release with a well-tested Python version:

.. code-block:: bash

   TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='xonsh[full]' \
    /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"

Install xonsh from the ``main`` Git branch with a stable Python version

.. code-block:: bash

   TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='git+https://github.com/xonsh/xonsh#egg=xonsh[full]' \
    /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"


Preinstall and preload `xontribs <https://github.com/topics/xontrib>`_:

.. code-block:: bash

   TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='git+https://github.com/xonsh/xonsh#egg=xonsh[full]' \
    PIP_INSTALL="uv xontrib-sh xontrib-jump-to-dir xontrib-dalias xontrib-pipeliner xontrib-whole-word-jumping" \
    XONSHRC="\$XONSH_HISTORY_BACKEND = 'sqlite'; xontrib load -s sh jump_to_dir pipeliner whole_word_jumping dalias; \$PROMPT = \$PROMPT.replace('{prompt_end}', '\n{prompt_end}')" \
    /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"

Usage
=====

After installation, you no longer need to worry about Python or package
manipulations unintentionally breaking the shell. You can safely use ``pip``,
``brew``, and other package managers without corrupting the xonsh environment.

After installation:

* ``xonsh`` refers to ``~/.local/xonsh-env/xbin/xonsh``.
* ``xpython`` refers to ``~/.local/xonsh-env/bin/python``.
* ``xpip`` refers to ``~/.local/xonsh-env/bin/python -m pip``.
* ``xcontext`` shows the current context.
* You can run ``source xmamba.xsh`` to activate mamba (see below).

Additions:

* ``xbin-xonsh`` runs xonsh from xonsh-env if ``xonsh`` is overridden in ``$PATH``.
* ``xbin-python`` runs Python from xonsh-env.
* Executable helpers from xonsh-env:

  * ``xbin-hidden`` lists the internal hidden ``bin`` directory of xonsh-env.
    Example: ``xpip install lolcat && xbin-hidden``.
  * ``xbin-add`` adds an executable from the hidden ``bin`` directory to the
    visible ``xbin``. Example: ``xbin-add lolcat``.
  * ``xbin-list`` lists executables in the visible ``xbin`` directory.
  * ``xbin-del`` removes an executable from ``xbin``. The executable remains in
    ``bin``.

Tips and Tricks
===============

Using mamba from xonsh-env
--------------------------

To bind the xonsh-env micromamba to the ``xmamba`` alias, run:

.. code-block:: console

   source xmamba.xsh

You can then use:

.. code-block:: console

   xmamba activate base  # Environment where xonsh was installed.
   pip install lolcat    # Install ``lolcat`` into the ``base`` environment.
   xmamba deactivate

   xmamba create --name myenv python=3.12
   xmamba activate myenv
   pip install lolcat    # Install ``lolcat`` into ``myenv``.
   xmamba deactivate

Cleaning
--------

If you do not plan to use ``xmamba``, you can reclaim disk space using
`mamba clean <https://fig.io/manual/mamba/clean>`_:

.. code-block:: console

   source xmamba.xsh
   xmamba clean -a

Uninstall
=========

Simply delete ``$TARGET_DIR``. For example:

.. code-block:: console

   rm -rf ~/.local/xonsh-env/

Known Issues
============

Do not blindly use as a login shell
----------------------------------

Using xonsh as a `login shell <https://linuxhandbook.com/login-shell/>`_ is not
recommended unless you are experienced and understand the implications. Many
tools expect the login shell to be POSIX-compliant, and issues may arise when
such tools attempt to run POSIX-specific commands in xonsh.

``std::bad_alloc``
------------------

If you encounter the error::

   terminate called after throwing an instance of 'std::bad_alloc'

delete the target directory (for example, ``rm -rf ~/.local/xonsh-env/``) and
repeat the installation.
