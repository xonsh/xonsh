Portable rootless xonsh build on AppImage
=========================================

`AppImage <https://appimage.org/>`_ is a format for distributing portable software on Linux without needing superuser permissions to install the application. It tries also to allow Linux distribution-agnostic binary software deployment for application developers, also called Upstream packaging. 

AppImage allows xonsh to be run on any AppImage supported Linux distributive without installation and root access.

.. raw:: html
	
	<p align="center"><a href="https://asciinema.org/a/9AH5AtYxbrn5nRo83nm46Z34n" target="_blank"><img src="https://asciinema.org/a/9AH5AtYxbrn5nRo83nm46Z34n.svg" /></a></p>

Try it now
----------
You can download and try `prebuilded xonsh.AppImage <https://github.com/anki-code/appimage-xonsh>`_:

.. code-block:: bash

	wget https://github.com/anki-code/appimage-xonsh/raw/master/xonsh-x86_64.AppImage && chmod +x xonsh-x86_64.AppImage
	./xonsh-x86_64.AppImage
	./xonsh-x86_64.AppImage --help


Build xonsh.AppImage
--------------------

Let's start:

1. Run docker with ``fuse``:

.. code-block:: bash

	sudo docker run --rm -it --privileged --device /dev/fuse -v `pwd`:/appimage ubuntu:16.04 bash


2. Install libraries for future building:

.. code-block:: bash

	apt update -y && apt upgrade -y
	apt install -y fuse wget mc \
			build-essential python-dev python-setuptools python-pip python-smbus \
			libncursesw5-dev libgdbm-dev libc6-dev  \
			zlib1g-dev libsqlite3-dev tk-dev \
			libssl-dev openssl \
			libffi-dev autoconf libfuse-dev

Not all required. Feel free to clean.

3. Getting the build scripts based on `linuxdeploy plugin python <https://github.com/niess/linuxdeploy-plugin-python>`_:

.. code-block:: bash

	mkdir -p /appimage && cd /appimage
	wget https://github.com/anki-code/linuxdeploy-plugin-python/archive/entrypoint.zip -O linuxdeploy-plugin-python-entrypoint.zip
	unzip linuxdeploy-plugin-python-entrypoint.zip

Here we see downloading of ``entrypoint`` branch from ``anki-code/linuxdeploy-plugin-python`` because the origin ``niess/linuxdeploy-plugin-python`` repository has not yet accepted the `pull request with xonsh <https://github.com/niess/linuxdeploy-plugin-python/pull/11>`_.

4. Building:

.. code-block:: bash

	cd linuxdeploy-plugin-python-entrypoint/appimage
	./build-python.sh xonsh
	cd ../ && ls -l

As result you'll find executable file ``xonsh-x86_64.AppImage`` that runs xonsh and can take command line arguments like xonsh:

.. code-block:: bash

	# ./xonsh-x86_64.AppImage -c "echo @(1+1)"
	2

Enjoy!

Troubleshooting
---------------

GLIBs versions
~~~~~~~~~~~~~~
You can noticed that we build AppImage in docker with older version of Ubuntu (16.04) to avoid error with core libraries versions when binary compiled on modern version can't use older version of libraries. In this nasty case you can see the error like ``/xonsh-x86_64.AppImage: /lib/x86_64-linux-gnu/libc.so.6: version GLIBC_2.25 not found (required by /ppp/xonsh-x86_64.AppImage)``. This means you should rebuild the AppImage for older version of distributive. If you know how to fix it once and forever feel free to tell us.

Windows Subsystem for Linux v1 (WSL1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Need WSL support:

.. code-block:: bash

	wsl1# ./xonsh-x86_64.AppImage
	fuse: device not found, try 'modprobe fuse' first

	Cannot mount AppImage, please check your FUSE setup.
	You might still be able to extract the contents of this AppImage
	if you run it with the --appimage-extract option.
	See https://github.com/AppImage/AppImageKit/wiki/FUSE
	for more information
	open dir error: No such file or directory

Workaround is extracting appimage and run manually:

.. code-block:: bash

	wsl1$ ./xonsh --appimage-extract
	wsl1$ ./squashfs-root/usr/bin/python3.7
