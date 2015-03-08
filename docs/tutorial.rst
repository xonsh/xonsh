.. _tutorial:

*******************
Tutorial
*******************
xonsh is shell language and command prompt. Unlike other shells, xonsh is 
based on Python with additional syntax added that makes calling subprocess
commands, manipulating the environment, and dealing with the file system easy. 
The xonsh command prompt give the users interactive access to the xonsh 
language. 

While all Python code is also xonsh, not all BASH code can be used in xonsh.
That would defeat the purpose and Python is better anyway! Still, xonsh is
BASH-wards compatible in the ways that matter, such as for running commands, 
reading in the BASH environment, and utilizing BASH tab completion.

The purpose of this tutorial is to teach you xonsh. There are many excellent
guides out there for learning Python and this will not join their ranks.
Similarly, you'd probably get the most out of this tutorial if you have 
already used a command prompt or interactive interpreter. 

Let's dive in!

Starting xonsh
========================
Assuming you have successfully installed xonsh (see http://xonsh.org),
you can start up the xonsh interpreter via the ``xonsh`` command. Suppose
you are in a lesser terminal:

.. code-block:: bash

    bash $ xonsh
    snail@home ~ $

Now we are in a xonsh shell. Our username happens to be ``snail``, our
hostname happens to be ``home``, and we are in our home directory (``~``).
Alternatively, you can setup your terminal emulator (xterm, gnome-terminal, 
etc) to run xonsh automatically when it starts up. This is recomended.

Basics
=======================
The xonsh language is based on Python and the xonsh shell uses Python to 
interpret any input it recieves. This makes simple things, like arithmetic, 
simple:

.. code-block:: python

    >>> 1 + 1
    2

.. note:: From here on we'll be using ``>>>`` to prefix (or prompt) any 
          xonsh input. This follows the Python convention and helps trick 
          syntax highlighting, though ``$`` is more traditional for shells.

Since this is just Python, we are able import modules, print values, 
and use other built-in Python functionality:

.. code-block:: python

    >>> import sys
    >>> print(sys.version)
    3.4.2 |Continuum Analytics, Inc.| (default, Oct 21 2014, 17:16:37) 
    [GCC 4.4.7 20120313 (Red Hat 4.4.7-1)]


We can also create and use literal data types, such as ints, floats, lists,
sets, and dictionaries. Everything that you are used to if you already know 
Python is there:

.. code-block:: python

    >>> d = {'xonsh': True}
    >>> d.get('bash', False)
    False

The xonsh shell also supports multiline input, for more advanced flow control.
The multiline mode is automatically entered whenever the first line of input
is not syntactically valid on its own. Multiline mode is then exited when 
enter (or return) is pressed when the cursor is in the first column.

.. code-block:: python

    >>> if True:
    ...     print(1)
    ... else:
    ...     print(2)
    ...
    1

.. note:: The multiline ``...`` continuation prompt is not present in xonsh.
          It is provided here for clarity and because helps trick 
          syntax highlighting again.

Flow control, of course, includes loops.

.. code-block:: python

    >>> for i, x in enumerate('xonsh'):
    ...     print(i, x)
    ...
    0 x
    1 o
    2 n
    3 s
    4 h

We can also define and call functions and classes. I'll mostly spare you the 
details, but this *is* pretty cool:

.. code-block:: python

    >>> def f():
    ...     return "xonsh"
    ...
    >>> f()
    'xonsh'

And that about wraps it up for the basics section.