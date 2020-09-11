Via AppImage
=============

`AppImage <https://appimage.org/>`_ is a format for distributing portable software on Linux without needing superuser permissions to install the application. It tries also to allow Linux distribution-agnostic binary software deployment for application developers, also called Upstream packaging. 

In short the AppImage is the one executable file which contains the xonsh and Python. AppImage allows xonsh to be run on any AppImage supported Linux distributives without installation and root access.

Get AppImage from Github
------------------------
You can get xonsh AppImage from Github and run it on your Linux without install:

.. code-block:: bash

    wget https://github.com/xonsh/xonsh/releases/latest/download/xonsh-x86_64.AppImage -O xonsh
    chmod +x xonsh
    ./xonsh

If you haven't Python on your host you may want to get it from AppImage:

.. code-block:: xonsh

    ./xonsh
    $PATH = [f'{$APPDIR}/usr/bin'] + $PATH
    python -m pip install tqdm --user  # the package will be installed to ~/.local/
    import tqdm

Building your own xonsh AppImage
--------------------------------

The best way to build xonsh AppImage in 5 minutes is to using `python-appimage <https://github.com/niess/python-appimage>`_:

.. code-block:: bash

    mkdir -p /tmp/build && cd /tmp/build
    git clone --depth 1 https://github.com/xonsh/xonsh
    cd xonsh/appimage
    echo 'xonsh' > requirements.txt
    cat pre-requirements.txt >> requirements.txt  # here you can add your additional PyPi packages to pack them into AppImage
    cd ..    
    pip install git+https://github.com/niess/python-appimage
    python -m python_appimage build app ./appimage
    ./xonsh-x86_64.AppImage
