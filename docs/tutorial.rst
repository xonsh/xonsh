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

And that about wraps it up for the basics section. It is just like Python.

Environment Variables
=======================
Environment variables are written as ``$`` followed by a name.  For example, 
``$HOME``, ``$PWD``, and ``$PATH``. 

.. code-block:: python

    >>> $HOME
    '/home/snail'

You can set (and export) environment variables like you would set any other 
variable in Python.  The same is true for deleting them too.

.. code-block:: python

    >>> $GOAL = 'Become the Lord of the Files'
    >>> print($GOAL)
    Become the Lord of the Files
    >>> del $GOAL

Very nice. All environment variables live in the built-in 
``__xonsh_env__`` mapping. You can access this mapping directly, but in most 
situations, you shouldn't need to.

Like other variables in Python, environment variables have a type. Sometimes
this type is imposed based on the variable name. The current rules are pretty
simple:

* ``PATH``: any variable whose name contains PATH is a list of strings.
* ``XONSH_HISTORY_SIZE``: this variable is an int.

xonsh will automatically convert back and forth to untyped (string-only)
representations of the environment as needed (mostly by subprocess commands).
When in xonsh, you'll always have the typed version.  Here are a couple of 
PATH examples:

.. code-block:: python

    >>> $PATH
    ['/home/snail/.local/bin', '/home/snail/sandbox/bin', 
    '/home/snail/miniconda3/bin', '/usr/local/bin', '/usr/local/sbin', 
    '/usr/bin', '/usr/sbin', '/bin', '/sbin', '.']
    >>> $LD_LIBRARY_PATH
    ['/home/scopatz/.local/lib', '']

Also note that *any* Python object can go into the environment. It is sometimes
useful to have more sophisticated types, like functions, in the enviroment.
There are handful of environment variables that xonsh considers special.
They can be seen in the table below:

================== =========================== ================================
variable           default                     description
================== =========================== ================================
PROMPT             xosh.environ.default_prompt The prompt text, may be str or 
                                               function which returns a str.
MULTILINE_PROMPT   ``'.'``                     Prompt text for 2nd+ lines of
                                               input, may be str or 
                                               function which returns a str.
XONSHRC            ``'~/.xonshrc'``            Location of run control file
XONSH_HISTORY_SIZE 8128                        Number of items to store in the
                                               history.
XONSH_HISTORY_FILE ``'~/.xonsh_history'``      Location of history file
================== =========================== ================================

Customizing the prompt is probably the most common reason for altering an 
environment variable.

Environment Lookup with ``${}``
================================
The ``$NAME`` is great as long as you know the name of the environment 
variable you want to look up.  But what if you want to construct the name
programatically, or read it from another variable? Enter the ``${}`` 
operator.

.. warning:: In BASH, ``$NAME`` and ``${NAME}`` are syntactically equivalent.
             In xonsh, they have separate meanings.

While in Python-mode (not subprocess-mode, which we'll get to later), we can 
place any valid Python expressin inside of the curly braces in ``${<expr>}``. 
This result of this expression will then be used to look up a value in 
the environment.  In fact, ``${<expr>}`` is the same as doing 
``__xonsh_env__[<expr>]``, but much nicer to look at. Here are a couple of 
examples in action:

.. code-block:: python

    >>> x = 'USER'
    >>> ${x}
    'snail'
    >>> ${'HO' + 'ME'}
    '/home/snail'

