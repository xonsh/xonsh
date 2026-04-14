**************************************
Xonsh Installation General Guide
**************************************

The guide is new so in case of error please open the issue in the `tracker <https://github.com/xonsh/xonsh/issues>`_.

Before Installing
========================

Xonsh is a full-featured shell and can technically be used as a login shell,
but since it is not a POSIX‑compatible shell, we don't recommend doing
so unless you clearly understand the purpose and consequences.
Do not attempt to set it as your default shell using ``chsh``
or by any other method that would replace the system shell.

The recommended practice is to create a Xonsh profile in your terminal emulator.


Overview
========================

Xonsh is a Python-based shell that requires Python to be packaged, preinstalled or compiled in order to run.
Since there are many ways to install Python, there are also many ways to run xonsh. The table describes
the main approaches and their advantages.

.. raw:: html

    <table class="docutils align-default">
      <thead>
        <tr>
          <th></th>
          <th class="head"><p>Use as <br>core shell</p></th>
          <th class="head"><p>Isolated env</p></th>
          <th class="head"><p>Fresh version</p></th>
          <th class="head"><p>Automation</p></th>
          <th class="head"><p>Portable</p></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th class="stub"><p>Independent install</p></th>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center">◯</td>
          <td align="center"></td>
        </tr>
        <tr>
          <th class="stub"><p>Package</p></th>
          <td align="center"></td>
          <td align="center"></td>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center"></td>
        </tr>
        <tr>
          <th class="stub"><p>AppImage</p></th>
          <td align="center"></td>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center">◯</td>
          <td align="center">🟢</td>
        </tr>
        <tr>
          <th class="stub"><p>Container</p></th>
          <td align="center"></td>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center">🟢</td>
          <td align="center"></td>
        </tr>
        <tr>
          <th class="stub"><p>System package</p></th>
          <td align="center"></td>
          <td align="center"></td>
          <td align="center">◯</td>
          <td align="center"></td>
          <td align="center"></td>
        </tr>
      </tbody>
    </table>

Work in progress:
`binary build <https://github.com/xonsh/xonsh/issues/2895#issuecomment-3665753657>`_,
`running in RustPython <https://github.com/xonsh/xonsh/issues/5082#issue-1611837062>`_,
`xonsh Flatpak <https://github.com/xonsh/xonsh-flatpak>`_.

Independent install
========================

When xonsh is used as a core shell, it is necessary to keep the Python environment with xonsh
stable, predictable, and independent of system changes. Lightweight environment managers
such as ``venv``, ``pipx``, or ``rye`` do not fully address this requirement.
Package managers that can install fully isolated Python environments as a core feature,
such as Miniconda or Micromamba, should be used.

Linux / macOS / WSL
-------------------

Install Xonsh independently using Micromamba:

.. code-block:: console

    $ TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='xonsh[full]' \
      /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"

Learn more: `Mamba installer <install_mamba.html>`_.


Windows
-------

.. note::

   The installation instructions for Windows were recently updated.
   If you run into any issues, please report them to the
   `issue tracker <https://github.com/xonsh/xonsh/issues>`_.

We provide an experimental Xonsh installer for Windows (no admin rights required). Download the ``.exe`` from the
`Xonsh WinGet releases page <https://github.com/xonsh/xonsh-winget/releases>`_:

* ``inno6`` — for Windows 10/11 (latest Python 3).
* ``inno5`` — for Windows 8.1+ (pinned to Python 3.13).

Or install via the script (no admin rights required):

.. code-block:: doscon

    > curl -L -o install_xonsh.cmd https://xon.sh/install/windows_install_xonsh.cmd
    > install_xonsh.cmd  # Install to ~/xonsh-env/

Package
========================

**pip:**

You can install xonsh package from PyPi using an existing installation of ``pip``, ``pipx``, ``rye``, etc.

.. code-block:: console

    $ pip install 'xonsh[full]'

Pip can also install the most recent xonsh source code from the
`xonsh project repository <https://github.com/xonsh/xonsh>`_:

.. code-block:: console

    $ pip install 'https://github.com/xonsh/xonsh/archive/main.zip#egg=xonsh[full]'

**mamba:**

.. code-block:: console

    $ mamba install xonsh

**conda:**

.. code-block:: console

    $ conda config --add channels conda-forge
    $ conda install xonsh


AppImage
========================

Xonsh is available as a single AppImage bundled with Python, allowing you to run it on Linux without installation:

.. code-block:: console

    $ wget 'https://github.com/xonsh/xonsh/releases/latest/download/xonsh-x86_64.AppImage' -O xonsh
    $ chmod +x xonsh
    $ ./xonsh

Study how to package your libraries in `Xonsh AppImage <appimage.html>`_ article.

Container
========================

Xonsh publishes a handful of containers, primarily targeting CI and automation use cases.
All of them are published on `Docker Hub <https://hub.docker.com/u/xonsh>`__.

Example of running an interactive xonsh session in a container:

.. code-block:: console

    $ docker run --rm -it xonsh/interactive

Learn more: `Containers <containers.html>`_.


System package
========================

Various operating system distributions provide platform-specific package managers that may offer a xonsh package.
This approach is **not recommended** for the following reasons:

* On non-rolling-release operating systems, the xonsh version is often outdated.
* The package may be missing important dependencies.
* System package managers install xonsh into the system Python environment, which means that any significant system update or change has a high probability of breaking the shell.

**Arch Linux:**

.. code-block:: console

    $ pacman -S xonsh  # not recommended but possible

**Debian/Ubuntu:**

.. code-block:: console

    $ apt install xonsh  # not recommended but possible

**Fedora:**

.. code-block:: console

    $ dnf install xonsh  # not recommended but possible

**GNU guix:**

.. code-block:: console

    $ guix install xonsh  # not recommended but possible

**macOS:**

.. code-block:: console

    $ brew install xonsh  # not recommended but possible

WIP Binary build
========================

Using Nuitka (a Python compiler), it is possible to build a binary version of xonsh.
Learn more in `xonsh/2895 <https://github.com/xonsh/xonsh/issues/2895>`_.

WIP RustPython build
========================

Using RustPython (a Python Interpreter written in Rust), it is possible to run xonsh using Rust.
Learn more in `xonsh/5082 <https://github.com/xonsh/xonsh/issues/5082>`_.


Updating xonsh
========================

How you update xonsh depends on the install method.

**xonsh installed via pip**

If xonsh was installed via pip (possibly into a virtual environment), you can
update it from within xonsh itself using :ref:`xpip <aliases-xpip>` — a
predefined alias pointing to the ``pip`` command associated with the Python
executable that runs the current xonsh session:

.. code-block:: xonshcon

   @ xpip install --upgrade xonsh  # install the latest release
   @ xpip install -U --force-reinstall git+https://github.com/xonsh/xonsh  # install from the repository

**xonsh installed via a package manager**

If you installed xonsh via a package manager, it is recommended to update it
through the package manager's appropriate command. For example, on macOS with
homebrew:

.. code-block:: console

   $ brew upgrade xonsh


.. _default_shell:

Setting xonsh as the default shell
========================================

Setting xonsh as your default login shell is **not recommended**.
Xonsh is a full-featured shell and can technically be used as a login
shell, but since it is not POSIX-compatible, system scripts and tooling
that expect a POSIX shell may misbehave. Use it only if you clearly
understand the purpose and consequences — see the rationale in
`Before Installing`_ above. The recommended practice is to create a
xonsh profile in your terminal emulator instead.

If you still want to use xonsh as your default shell, you will have
to add xonsh to ``/etc/shells`` and switch:

.. code-block:: console

    $ which xonsh
    # which xonsh >> /etc/shells
    $ chsh -s $(which xonsh)

You will have to log out and log back in before the changes take effect.
