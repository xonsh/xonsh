.. _tutorial_subproc_strings:

************************************
Tutorial: Subprocess Strings
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
This is different from other shells, which have a different set of escape
sequences than Python has.  Notably, many sh-langs allow you to escape
spaces with ``"\ "`` (backslash-space).

**bash**

.. code-block:: bash

    $ echo A\ Single\ Argument
    A Single Argument

In the above example, since the spaces are escaped, the ``echo`` command
only receves a single argument. Xonsh does not allow this. If you were
to try this in xonsh, you'd see:

**xonsh**

.. code-block:: bash

    $ echo Actually\ Three\ Arguments
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
`Subprocess Macros <tutorial_macros.html#subprocess-macros>`_,
these allow all input following an ``!`` to be treated as a single argument.
For example,

**xonsh**

.. code-block:: bash

    $ echo! A  Single     Argument
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

.. code-block:: bash

    $ echo foo"bar"baz
    foo"bar"baz

    $ echo --key="value"
    --key="value"

You can think of these being equivalent to,


**xonsh**

.. code-block:: bash

    $ echo 'foo"bar"baz'
    foo"bar"baz

    $ echo '--key="value"'
    --key="value"

This is yet another major point of departure for xonsh from traditional
shells. However, the xonsh subprocess string handling is
consistent and predictable.

Further Reading
===============
For deeper details on the great string debate, please feel free to read
and comment at:

* `To Quote or Not Quote <https://github.com/xonsh/xonsh/issues/1432>`_
* `Quote removal in subprocess mode does not behave as expected <https://github.com/xonsh/xonsh/issues/621>`_
