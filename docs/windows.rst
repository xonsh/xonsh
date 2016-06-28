==========================
Windows Guide
==========================

Installation
================

The easy way
----------------

The easiest way to install xonsh on windows is through the Anaconda Python
Distribution and the conda package manager.

.. note::

    Be sure to install the version with Python3.4 or later.
    Xonsh is not yet supported on legacy Python (2.7).

Install xonsh with the following command:

.. code-block:: bat

   > conda config --add channels conda-forge
   > conda install xonsh

.. note:: For the bleeding edge development version use ``conda install -c xonsh/channel/dev xonsh``

This will install xonsh and all the recommended dependencies. Next, run xonsh:

.. code-block:: bat

   > xonsh
   snail@home ~ $


Install from source
-------------------

To install xonsh from source on Windows, first install `Python v3.4+`_ from
http://python.org. Remember to select "Add python to PATH" during installation.

Next, install the prompt_toolkit dependency via ``pip``:

.. code-block:: bat

   > pip install prompt-toolkit

While prompt-toolkit is considered an optional dependency, it is the
recommended alternative to pyreadline for Windows users. For Windows,
it is recommended to use a replacement console emulator. Good choices are `cmder`_ or `conemu`_.

Download the latest `xonsh-master.zip`_ from github and unzip it
to ``xonsh-master``.

Now install xonsh:

.. code-block:: bat

   > cd xonsh-master
   > python setup.py install

Next, run xonsh:

.. code-block:: bat

  > xonsh
  snail@home ~ $

.. _Python v3.4+: https://www.python.org/downloads/windows/
.. _xonsh-master.zip: https://github.com/xonsh/xonsh/archive/master.zip
.. _cmder: http://cmder.net/
.. _conemu: https://conemu.github.io/

Usage
================

Name space conflicts
--------------------

Due to ambiguity with the Python ``dir`` builtin, to list the current
directory via the ``cmd.exe`` builtin you must explicitly request
the ``.``, like this:

.. code-block:: xonshcon

   >>> dir .
    Volume in drive C is Windows
    Volume Serial Number is 30E8-8B86

    Directory of C:\Users\snail\xonsh

   2015-05-12  03:04    <DIR>          .
   2015-05-12  03:04    <DIR>          ..
   2015-05-01  01:31    <DIR>          xonsh
                  0 File(s)              0 bytes
                  3 Dir(s)  11,008,000,000 bytes free



Many people create a ``d`` alias for the ``dir`` command to save
typing and avoid the ambiguity altogether:

.. code-block:: xonshcon

   >>> aliases['d'] = ['cmd', '/c', 'dir']

You can add aliases to your ``~/.xonshrc`` to have it always
available when xonsh starts.


Unicode support for Windows
----------------------------

Python's utf-8 unicode is not compatible with the default shell 'cmd.exe' on Windows. The package ``win_unicode_console`` fixes this. Xonsh will use ``win_unicode_console`` if it is installed. This can be disabled/enabled with the ``$WIN_UNICODE_CONSOLE``` environment variable.

.. note:: Even with unicode support enabled the symbols available will depend on the font used in cmd.exe.

The packages ``win_unicode_console`` can be installed using pip or conda.

.. code-block:: bat

  > pip install win_unicode_console


.. code-block:: bat

  > conda install --channel xonsh win_unicode_console
