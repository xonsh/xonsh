.. _env:

Environment
===========

Basics
------

Environment variables are written as ``$`` followed by a name (e.g. ``$HOME``,
``$PWD``, ``$PATH``).  They can be set, deleted, and used just like regular
Python variables.

For a full introduction see the :ref:`Environment Variables <tutorial>` section
of the tutorial.

Temporary Variables with ``swap``
---------------------------------

Use ``@.env.swap()`` to set environment variables for the duration of a
``with`` block.  The original values are restored automatically when the
block exits, even if an exception is raised:

.. code-block:: xonsh

    with @.env.swap(PGPASSWORD=@.imp.getpass.getpass('pgpass:')):
        for db in ['db1', 'db2']:
            psql postgresql://user@host:5439/@(db) -c 'select 1'

    # $PGPASSWORD is unset here

Multiple variables can be swapped at once:

.. code-block:: xonsh

    with @.env.swap(LANG='C', LC_ALL='C'):
        sort data.txt

Registering Environment Variables
---------------------------------

You can manually register environment variables to define their type and documentation.
This is particularly useful for extensions or complex configurations. The documentation provided
will be shown during tab-completion.

.. code-block:: xonsh

    @.env.register('MY_VAR1', type='int', default=1, doc='Demo variable 1.')
    @.env.register('MY_VAR2', type='int', default=2, doc='Demo variable 2.')

Now, when you type ``$MY_<Tab>``, you will see the description.

Available types: ``"bool"``, ``"str"``, ``"int"``, ``"float"``, ``"path"``,
``"env_path"``, ``"abs_path"``.  To get the current list:

.. code-block:: xonshcon

    @ list(@.imp.xonsh.environ.ENSURERS.keys())
    ['bool', 'str', 'path', 'env_path', 'abs_path', 'float', 'int', 'var_pattern']

Getting Help on a Variable
--------------------------

Use the ``$VAR?`` syntax to see the description, default value, and other
metadata of any environment variable:

.. code-block:: xonshcon

    @ $XONSH_COMMANDS_CACHE_READ_DIR_ONCE?
    Name: $XONSH_COMMANDS_CACHE_READ_DIR_ONCE
    Description: List of directory prefixes whose contents are cached on first
    access and never re-read within the session.
    Default: []
    Configurable: True

This works for both built-in and registered variables.

Variable Patterns (``VarPattern``)
----------------------------------

Xonsh allows defining **pattern rules** that automatically apply type handling
to environment variables whose names match a regex pattern.  This is powered by
the ``VarPattern`` class.

Built-in patterns
^^^^^^^^^^^^^^^^^

Xonsh ships with two default patterns:

* ``$XONSH_ENV_PATTERN_PATH`` -- variables ending with ``PATH`` are treated as
  ``env_path`` (e.g. ``$MYPATH``, ``$LD_LIBRARY_PATH``).
* ``$XONSH_ENV_PATTERN_DIRS`` -- variables ending with ``DIRS`` are treated as
  ``env_path`` (e.g. ``$XDG_DATA_DIRS``).

Creating a pattern
^^^^^^^^^^^^^^^^^^

Set a ``VarPattern`` value directly:

.. code-block:: xonsh

    $XONSH_ENV_PATTERN_NUM = @.imp.xonsh.environ.VarPattern(r"\w*_NUM$", "int")

Or register with a default value and documentation:

.. code-block:: xonsh

    @.env.register(
        "XONSH_ENV_PATTERN_NUM",
        type="var_pattern",
        default=@.imp.xonsh.environ.VarPattern(r"\w*_NUM$", "int"),
        doc="Pattern rule: env vars matching *_NUM are treated as int.",
    )

Usage
^^^^^

Once a pattern is active, matching variables are automatically converted:

.. code-block:: xonshcon

    @ $QWE_NUM = '42'
    @ type($QWE_NUM)
    int

Excluding variables from a pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some variables may match a pattern but have different meaning.  Add them to
the ``exclude`` list:

.. code-block:: xonsh

    @ $XONSH_ENV_PATTERN_DIRS.exclude.append('JUPYTER_PLATFORM_DIRS')
    @ $JUPYTER_PLATFORM_DIRS = '1'
    @ $JUPYTER_PLATFORM_DIRS
    '1'

Disabling patterns
^^^^^^^^^^^^^^^^^^

Set a pattern variable to ``None`` to disable it entirely:

.. code-block:: xonsh

    $XONSH_ENV_PATTERN_DIRS = None
    $XONSH_ENV_PATTERN_PATH = None


See also
========

* :doc:`envvars` -- full list of environment variables
* :doc:`strings` -- environment variable substitution in strings
* :doc:`launch` -- passing variables via ``-D`` at startup
* :doc:`xonshrc` -- setting variables in RC files
