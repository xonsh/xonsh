*******************
Xonsh Installation General Guide
*******************

Overview
========================

Xonsh is a Python-based shell that requires Python to be packaged, preinstalled or compiled in order to run.
Since there are many ways to install Python, there are also many ways to run xonsh. The table describes
the main approaches and their advantages.

.. list-table::
    :widths: 3 1 1 1 1 1
    :header-rows: 1
    :stub-columns: 1

    * -
      - Use as core shell
      - Isolated env
      - Fresh version
      - Automation
      - Portable
    * - Independent install
      - ✓
      - ✓
      - ✓
      -
      -
    * - PyPi package
      -
      -
      - ✓
      - ✓
      -
    * - AppImage
      -
      - ✓
      - ✓
      -
      - ✓
    * - Conainer
      -
      - ✓
      - ✓
      - ✓
      -
    * - Platform package
      -
      -
      -
      -
      -

Independent install
========================

When xonsh is used as a core shell, it is necessary to keep the Python environment with xonsh
stable, predictable, and independent of system changes. Lightweight environment managers
such as ``venv``, ``pipx``, or ``rye`` do not fully address this requirement.
Package managers that can install fully isolated Python environments as a core feature,
such as Miniconda or Micromamba, should be used.

Install xonsh with Micromamba:

.. code-block:: console

    TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='xonsh[full]' \
      /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"

Learn more: `Mamba installer <install_mamba.html>`_.


PyPi package
========================

You can install xonsh package from PyPi using an existing installation of ``pip``, ``pipx``, ``rye``, etc.

**pip:**

.. code-block:: console

    pip install 'xonsh[full]'  # or just xonsh for minimal dependencies

Pip can also install the most recent xonsh source code from the
`xonsh project repository <https://github.com/xonsh/xonsh>`_:

.. code-block:: console

    pip install 'https://github.com/xonsh/xonsh/archive/main.zip#egg=xonsh[full]'


**conda:**

.. code-block:: console

    conda config --add channels conda-forge
    conda install xonsh


AppImage
========================

Xonsh is available as a single AppImage bundled with Python, allowing you to run it on Linux without installation:

.. code-block:: console

    wget 'https://github.com/xonsh/xonsh/releases/latest/download/xonsh-x86_64.AppImage' -O xonsh
    chmod +x xonsh
    ./xonsh

Learn more: `Xonsh AppImage <appimage.html>`_.

Container
========================

Xonsh publishes a handful of containers, primarily targeting CI and automation use cases.
All of them are published on `Docker Hub <https://hub.docker.com/u/xonsh>`__.

Example of running an interactive xonsh session in a container:

.. code-block:: console

    docker run --rm -it xonsh/interactive

Learn more: `Containers <containers.html>`_.


Platform package
========================

Various operating system distributions provide platform-specific package managers that may offer a xonsh package.
This approach is **not recommended** for the following reasons:

* On non-rolling-release operating systems, the xonsh version is often outdated and may lack important dependencies.
* System package managers install xonsh into the system Python environment, which means that any significant system update or change has a high probability of breaking the shell.

**Arch Linux:**

.. code-block:: console

    pacman -S xonsh

**Debian/Ubuntu:**

.. code-block:: console

    apt install xonsh


**Fedora:**

.. code-block:: console

    dnf install xonsh

**GNU guix:**

.. code-block:: console

    guix install xonsh

**OSX:**

.. code-block:: console

    brew install xonsh

WIP Binary build
========================

Using Nuitka (a Python compiler), it is possible to build a binary version of xonsh.
Learn more in `xonsh/2895 <https://github.com/xonsh/xonsh/issues/2895>`_.

WIP RustPython build
========================

Using RustPython (a Python Interpreter written in Rust), it is possible to run xonsh using Rust.
Learn more in `xonsh/5082 <https://github.com/xonsh/xonsh/issues/5082>`_.

See also
========================

.. toctree::
    :titlesonly:
    :maxdepth: 2

    platform-issues
