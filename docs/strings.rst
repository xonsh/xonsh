.. _strings:
.. _subproc_strings:

************************************
Subprocess Strings
************************************
Strings in xonsh follow two simple rules:

1. Strings in xonsh are always parsed in the same way, and
2. Python always wins!

Together these rules mean that **even strings in subprocess mode are treated
like Python strings!** This will (help) preserve your sanity.

No Escape
=========
Xonsh strings are exactly like Python strings everywhere. Xonsh uses
exactly the same escape characters that Python does; no more and no less.

**bash**

.. code-block:: bash

    $ echo A\ Single\ Argument
    A Single Argument

In the above example, since the spaces are escaped, the ``echo`` command
only receves a single argument. Xonsh does not allow this. If you were
to try this in xonsh, you'd see:

**xonsh**

.. code-block:: xonshcon

    @ echo Actually\ Three\ Arguments
    Actually\ Three\ Arguments

In this example, echo recives three arguments:: ``"Actually\\"``, ``"Three\\"``,
and ``"Arguments"``. Instead, xonsh requires you to use quotes in order to
pass in a single argument:

**xonsh** or **bash**

.. code-block:: bash

    $ echo "A Single Argument"
    A Single Argument

Using quotes is arguably what should have been done in sh-lang in the
first place.

.. note::

    When in doubt in subprocess mode, use quotes!


Justification
=============
The reasons for not having additional escape sequences, as in sh-langs, are:

1. Escape charaters can get overwhemlingly ugly, fast.
2. We have escape characters, they are called quotes :)
3. We have literal input in subprocess mode via macros.

On this last point, if you don't already know about
`Subprocess Macros <macros.html#subprocess-macros>`_,
these allow all input following an ``!`` to be treated as a single argument.
For example,

**xonsh**

.. code-block:: xonshcon

    @ echo! A  Single     Argument
    A  Single     Argument

Subprocess macros are the ultimate escape mechanism.

The Quotes Stay
===============
In sh-langs, internal quote characters are removed. For instance:

.. code-block:: bash

    $ echo foo"bar"baz
    foobarbaz

    $ echo --key="value"
    --key=value

Xonsh considers this behavior suboptimal. Instead, xonsh treats these
arguments as if they were surrounded in another, outer level of
quotation (``'foo"bar"baz'``). Xonsh will keep the quotation marks
when leading and trailing quotes are not matched.

**xonsh**

.. code-block:: xonshcon

    @ echo foo"bar"baz
    foo"bar"baz

    @ echo --key="value"
    --key="value"

You can think of these being equivalent to,


**xonsh**

.. code-block:: xonshcon

    @ echo 'foo"bar"baz'
    foo"bar"baz

    @ echo '--key="value"'
    --key="value"

This is yet another major point of departure for xonsh from traditional
shells. However, the xonsh subprocess string handling is
consistent and predictable.

Environment Variable Substitution
==================================

In subprocess mode, ``$NAME`` inside strings is replaced with the value
of the environment variable. This happens automatically for regular and
f-strings, but **not** for raw strings:

.. code-block:: xonsh

    echo $HOME
    # /home/snail

    echo "$HOME"
    # /home/snail

    echo r"$HOME"
    # $HOME           -- raw strings suppress substitution

    echo $HOME/docs    # subprocess mode -- substituted inline
    # /home/snail/docs

    del $MY_VAR

See `String Literal Prefixes`_ below for a full comparison of which
string types perform substitution.


String Literal Prefixes
=======================

For fine control of environment variable substitutions, brace substitutions,
and backslash escapes, xonsh supports an extended set of string literal
prefixes:

- ``""`` — regular string: backslash escapes. Envvar substitutions in subprocess mode.
- ``r""`` — raw string: unmodified.
- ``f""`` — formatted string: brace substitutions, backslash escapes. Envvar substitutions in subprocess mode.
- ``fr""`` — raw formatted string: brace substitutions.
- ``p""`` — path string: backslash escapes, envvar substitutions, returns Path.
- ``pr""`` — raw path string: envvar substitutions, returns Path.
- ``pf""`` — formatted path string: backslash escapes, brace and envvar substitutions, returns Path.

To understand the differences, set ``$EVAR`` to ``1`` and ``var`` to ``2``:

.. table::

    ========================  ==========================  =======================  =====================
         String literal            As python object       print(<String literal>)  echo <String literal>
    ========================  ==========================  =======================  =====================
    ``"/$EVAR/\'{var}\'"``    ``"/$EVAR/'{var}'"``        ``/$EVAR/'{var}'``       ``/1/'{var}'``
    ``r"/$EVAR/\'{var}\'"``   ``"/$EVAR/\\'{var}\\'"``    ``/$EVAR/\'{var}\'``     ``/$EVAR/\'{var}\'``
    ``f"/$EVAR/\'{var}\'"``   ``"/$EVAR/'2'"``            ``/$EVAR/'2'``           ``/1/'2'``
    ``fr"/$EVAR/\'{var}\'"``  ``"/$EVAR/\\'2\\'"``        ``/$EVAR/\'2\'``         ``/$EVAR/\'2\'``
    ``p"/$EVAR/\'{var}\'"``   ``Path("/1/'{var}'")``      ``/1/'{var}'``           ``/1/'{var}'``
    ``pr"/$EVAR/\'{var}\'"``  ``Path("/1/\\'{var}\\'")``  ``/1/\'{var}\'``         ``/1/\'{var}\'``
    ``pf"/$EVAR/\'{var}\'"``  ``Path("/1/'2'")``          ``/1/'2'``               ``/1/'2'``
    ========================  ==========================  =======================  =====================


String Tricks
=============

Triple Quotes
-------------

To avoid escape characters (e.g. ``echo "\"hello\""``), use triple
quotes:

.. code-block:: xonsh

    echo """{"hello":'world'}"""
    # {"hello":'world'}

Creating Files with Multiline Strings
--------------------------------------

Combine triple quotes with ``@()`` and a redirect to create files
without heredoc syntax:

.. code-block:: xonsh

    echo @("""
    line 1
    line 2
    line 3
    """.strip()) > file.txt

Multiline Arguments
-------------------

Use ``@()`` with triple quotes to pass a multiline string as a single
argument:

.. code-block:: xonsh

    python -c @("""
    import sys
    for i in range(3):
        print(i, sys.platform)
    """)

f-strings in Commands
---------------------

You can use ``@()`` to inject an f-string, but f-strings also work
directly in subprocess mode:

.. code-block:: xonsh

    echo @(f'Hello {$HOME}')
    # Hello /home/snail

    # f-strings work by themselves too:
    echo f'Hello {$HOME}'
    # Hello /home/snail


Splitting Strings Like the Shell
---------------------------------

Xonsh's :meth:`Lexer.split() <xonsh.parsers.lexer.Lexer.split>` can
split a string into tokens the same way the shell does -- respecting
quoting, escapes, and operators.  This is the function used internally
by the ``@$()`` operator:

.. code-block:: python

    from xonsh.parsers.lexer import Lexer
    Lexer().split('echo "hello world" file.txt')
    # ['echo', '"hello world"', 'file.txt']


See also
========

* :doc:`subprocess` -- subprocess operators and capturing modes
* :doc:`env` -- environment variables and ``@.env.swap()``
* :doc:`globbing` -- glob and regex path expansion
* :doc:`macros` -- subprocess macros for literal input
* `To Quote or Not Quote <https://github.com/xonsh/xonsh/issues/1432>`_
* `Quote removal in subprocess mode does not behave as expected <https://github.com/xonsh/xonsh/issues/621>`_
