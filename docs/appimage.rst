Via AppImage
=============

`AppImage <https://appimage.org/>`_ is a format for distributing portable software on Linux without needing superuser permissions to install the application. It tries also to allow Linux distribution-agnostic binary software deployment for application developers, also called Upstream packaging. 

AppImage allows xonsh to be run on any AppImage supported Linux distributive without installation and root access.

The best way to build xonsh AppImage in 5 minutes is to using `python-appimage <https://github.com/niess/python-appimage>`_:

.. code-block:: bash

    mkdir -p /tmp/test && cd /tmp/test
    git clone https://github.com/niess/python-appimage
    cd python-appimage
    python -m python_appimage build app applications/xonsh
    ./xonsh-x86_64.AppImage
