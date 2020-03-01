Portable rootless xonsh build on AppImage
=========================================

`AppImage <https://appimage.org/>`_ is a format for distributing portable software on Linux without needing superuser permissions to install the application. It tries also to allow Linux distribution-agnostic binary software deployment for application developers, also called Upstream packaging. 

AppImage allows xonsh to be run on any AppImage supported Linux distributive without installation and root access.

.. raw:: html
	
	<p align="center"><a href="https://asciinema.org/a/9AH5AtYxbrn5nRo83nm46Z34n" target="_blank"><img src="https://asciinema.org/a/9AH5AtYxbrn5nRo83nm46Z34n.svg" /></a></p>

Try it now
----------
You can download and try `prebuilded xonsh.AppImage <https://github.com/niess/linuxdeploy-plugin-python/releases>`_:

.. code-block:: bash

	wget https://github.com/niess/linuxdeploy-plugin-python/releases/download/continuous/xonsh-x86_64.AppImage -O xonsh.AppImage
	chmod +x xonsh.AppImage
	./xonsh.AppImage -c "echo @(1+1)"
	./xonsh.AppImage

Build xonsh.AppImage
--------------------

`Dockerfile`
~~~~~~~~~~~~

.. code-block:: bash

	FROM ubuntu:16.04
	RUN apt update -y && apt upgrade -y
	RUN apt install --no-install-recommends -y -qq \
		fuse wget mc git \
		build-essential python-dev python-setuptools python-pip python-smbus \
		libncursesw5-dev lib32ncurses5-dev libgdbm-dev libc6-dev  \
		zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl libffi-dev autoconf \
		libfuse-dev libncurses5-dev libreadline-dev libdb5.3-dev libbz2-dev \
		libexpat1-dev liblzma-dev  automake libfuse2

	RUN mkdir -p /build /appimage
	WORKDIR /build
	RUN git clone --depth 1 https://github.com/niess/linuxdeploy-plugin-python && \
		cd linuxdeploy-plugin-python && \
		git checkout 85d2e6fac5969d1b381f4da384248b368522ede3
	CMD cd /build/linuxdeploy-plugin-python/appimage && ./build-python.sh xonsh && cp *.AppImage /appimage


`build.sh`
~~~~~~~~~~

.. code-block:: bash

	docker build --no-cache -t local/appimage-xonsh .
	docker run --rm --privileged --device /dev/fuse -v `pwd`:/appimage -it local/appimage-xonsh	

As result you'll find executable file ``xonsh-x86_64.AppImage`` that runs xonsh and can take command line arguments like xonsh. Enjoy!

Running portable python and pip
-------------------------------

If you need to use python and pip from portable `xonsh.AppImage` just set up directories in `~/.xonshrc`:

.. code-block:: xonsh

	# replace host python to xonsh.AppImage python
	$PATH = [$PYTHONHOME + '/bin'] + $PATH
	
	# setting up pip packages directory
	$PIP_TARGET='/tmp/xonsh/pip'
	import sys
	sys.path.append('/tmp/xonsh/pip')

And magic is here:

.. code-block:: xonsh

	xonsh$ pip3 install tqdm
	xonsh$ ls /tmp/xonsh/pip/
	tqdm
	xonsh$ python
	>>> import tqdm
	>>> tqdm
	<module 'tqdm' from '/tmp/xonsh/pip/tqdm/__init__.py'>
	>>> # nice!

Troubleshooting
---------------

Python ImportError: No module named site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xonsh

	xonsh$ python
	ImportError: No module named site

The error above was appeared because host machine python try to find right path for `site-packages`. The fix is just using python from AppImage by setting right path to it across `$PYTHONHOME` which was set by AppImage:

.. code-block:: xonsh

	xonsh$ $PATH = [$PYTHONHOME + '/bin'] + $PATH
	xonsh$ python
	Python 3.7.3
	>>> # success

GLIBs versions
~~~~~~~~~~~~~~
You can noticed that we build AppImage in docker with older version of Ubuntu (16.04) to avoid error with core libraries versions when binary compiled on modern version can't use older version of libraries. In this nasty case you can see the error like ``/xonsh-x86_64.AppImage: /lib/x86_64-linux-gnu/libc.so.6: version GLIBC_2.25 not found (required by /ppp/xonsh-x86_64.AppImage)``. This means you should rebuild the AppImage for older version of distributive. If you know how to fix it once and forever feel free to tell us.

Windows Subsystem for Linux v1 (WSL1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Need WSL support:

.. code-block:: bash

	wsl1# ./xonsh.AppImage
	fuse: device not found, try 'modprobe fuse' first

	Cannot mount AppImage, please check your FUSE setup.
	You might still be able to extract the contents of this AppImage
	if you run it with the --appimage-extract option.
	See https://github.com/AppImage/AppImageKit/wiki/FUSE
	for more information
	open dir error: No such file or directory

Workaround is extracting appimage and run manually:

.. code-block:: bash

	wsl1$ ./xonsh.AppImage --appimage-extract
	wsl1$ ./squashfs-root/usr/bin/python3.7 
