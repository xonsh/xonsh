*******************
Xonsh Installation General Guide
*******************

Overview
========================

Xonsh is a Python-based shell that requires Python to be packaged, preinstalled or compiled in order to run.
Since there are many ways to install Python, there are also many ways to run xonsh. The table describes
the main approaches and their advantages.

.. list-table::
    :widths: 3 1 1 1 1 1 1 1
    :header-rows: 1
    :stub-columns: 1

    * -
      - Isolated install
      - Python package
      - OS package
      - AppImage
      - Docker
      - WIP Binary build
      - WIP RustPython build
    * - Recommended
      - ✓
      -
      -
      -
      -
      -
      -
    * - Not recommended
      -
      -
      - ✓
      -
      -
      -
      -
    * - Isolated environment
      - ✓
      - ✓
      -
      - ✓
      -
      -
      -
    * - Fresh version
      - ✓
      - ✓
      -
      - ✓
      - ✓
      -
      -

Isolated install
========================



.. code-block:: console

    TARGET_DIR=$HOME/.local/xonsh-env PYTHON_VER=3.11 XONSH_VER='xonsh[full]' \
     /bin/bash -c "$(curl -fsSL https://xon.sh/install/mamba-install-xonsh.sh)"



Python package
========================

You can install xonsh using ``pip``, ``conda``, ``mamba`` and any package manager that support PyPi packages e.g. `pipx`.

**conda:**

.. code-block:: console

    $ conda config --add channels conda-forge
    $ conda install xonsh


**pip:** Typically you will activate a virtual environment and install xonsh there.  This will ensure that you invoke the
correct Python interpreter and ``pip`` module.

.. code-block:: console

    $ pip install 'xonsh[full]'  # or just xonsh for minimal dependencies

**source:** Pip can also install the most recent xonsh source code from the
`xonsh project repository <https://github.com/xonsh/xonsh>`_.

.. code-block:: console

    $ pip install pygments prompt-toolkit setproctitle https://github.com/xonsh/xonsh/archive/main.zip


OS package
========================

Various operating system distributions provide platform-specific package managers that may offer a xonsh package.
This approach is **not recommended** for the following reasons:

* On non-rolling-release operating systems, the xonsh version is often outdated and may lack important dependencies.
* System package managers install xonsh into the system Python environment, which means that any significant system update or change has a high probability of breaking the shell.


**Debian/Ubuntu:**

.. code-block:: console

    $ [sudo] apt install

**Fedora:**

.. code-block:: console

    $ [sudo] dnf install

**Arch Linux:**

.. code-block:: console

    $ [sudo] pacman -S

**OSX:**

.. code-block:: console

    $ [sudo] brew install


AppImage
========================

Docker
========================

WIP Binary build
========================

Using Nuitka (a Python compiler), it is possible to build a binary version of xonsh. Learn more in `2895 <https://github.com/xonsh/xonsh/issues/2895>`_.

WIP RustPython build
========================

Using RustPython (a Python Interpreter written in Rust), it is possible to run xonsh using Rust. Learn more in `5082 <https://github.com/xonsh/xonsh/issues/5082>`_.

See also
========================

.. toctree::
    :titlesonly:
    :maxdepth: 2

    platform-issues
