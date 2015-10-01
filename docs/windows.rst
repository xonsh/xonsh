==========================
Windows Guide
==========================

Installation
================
To install xonsh on Windows, first install `Python v3.4+`_ from
http://python.org .

Next, install the other dependencies via ``pip``:

.. code-block:: bat

   > pip install ply
   > pip install prompt-toolkit

While Prompt-toolkit is considered an optional dependency, it's the
recommended alternative to pyreadline for windows users.
Once installed, you have to enable prompt-toolkit by adding the following to
your ``~/.xonshrc`` file:

.. code-block:: bat

$SHELL_TYPE = 'prompt_toolkit'

Download the latest `xonsh-master.zip`_ from github and unzip it
to ``xonsh-master``.

Now install xonsh:

.. code-block:: bat

   > cd xonsh-master
   > python setup.py install

.. _Python v3.4+: https://www.python.org/downloads/release/python-343/
.. _xonsh-master.zip: https://github.com/scopatz/xonsh/archive/master.zip


Usage
================
Now you are ready to run xonsh:

.. code-block:: bat

   > scripts\xonsh
   snail@home ~ $

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

