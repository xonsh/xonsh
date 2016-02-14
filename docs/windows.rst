==========================
Windows Guide
==========================

Installation
================

The easy way
----------------

The easiest way to install xonsh on windows is to use the conda package manager. First download and install the `Anaconda Python Distribution`_ 

.. note:: Be sure to install the version with Python3.4 or 3.5. Xonsh does is not supported on lagacy Python (2.7). 

The run the following in a command prompt:

.. code-block:: bat

   > conda install xonsh --channel xonsh

This will install xonsh and all the recommended dependencies. Next, run xonsh:

.. code-block:: bat

   > xonsh
   snail@home ~ $


Install from source
-------------------
      
To install xonsh from source on Windows, first install `Python v3.4+`_ from
http://python.org .

Next, install the prompt_toolkit dependency via ``pip``:

.. code-block:: bat

   > pip install prompt-toolkit

While prompt-toolkit is considered an optional dependency, it's the
recommended alternative to pyreadline for Windows users. For Windows, 
it's recommended to use a replacement console emulator. Good choices are cmder or conemu.

Download the latest `xonsh-master.zip`_ from github and unzip it
to ``xonsh-master``.

Now install xonsh:

.. code-block:: bat

   > cd xonsh-master
   > python setup.py install
   
Next, run xonsh: 
   
.. code-block:: bat

  > scripts\xonsh
  snail@home ~ $

.. _Python v3.4+: https://www.python.org/downloads/windows/
.. _xonsh-master.zip: https://github.com/scopatz/xonsh/archive/master.zip


Usage
================
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

You can add this alias to your ``~/.xonshrc`` to have it always
available when xonsh starts.
