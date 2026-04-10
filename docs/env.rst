.. _env:

Environment
===========

Basics
------

Environment variables are written as ``$`` followed by a name (e.g. ``$HOME``,
``$PWD``, ``$PATH``).  They can be set, deleted, and used just like regular
Python variables:

.. code-block:: xonshcon

    @ $HOME
    '/home/snail'

    @ $GOAL = 'Master the shell'
    @ print($GOAL)
    Master the shell
    @ del $GOAL

You can also build values from other variables:

.. code-block:: xonshcon

    @ $NUM = "123"
    @ $EXT = $NUM + "456"
    @ $EXT
    '123456'
    @ $FNUM = "{FILLME}456".format(FILLME=$NUM)
    @ $FNUM
    '123456'
    @ "%s456" % $NUM
    '123456'

.. note::

   To update ``os.environ`` when the xonsh environment changes set
   :ref:`$UPDATE_OS_ENVIRON <update_os_environ>` to ``True``.


The Environment Itself ``@.env``
--------------------------------

All environment variables live in the built-in ``@.env`` mapping.
You can access this mapping directly, but in most situations you don't
need to.

To check whether a variable exists:

.. code-block:: xonshcon

   @ 'HOME' in @.env
   True

To get help on a specific variable:

.. code-block:: xonshcon

   @ @.env.help('XONSH_DEBUG')

You can also set a variable on the command line before launching xonsh:

.. code-block:: xonshcon

    @ $HELLO='snail' xonsh -c 'echo Hello $HELLO'
    Hello snail


Environment Lookup with ``${<expr>}``
-------------------------------------

``$NAME`` works when you know the variable name up front.  To construct
the name programmatically, use the ``${<expr>}`` operator -- any valid
Python expression can go inside the curly braces:

.. code-block:: xonshcon

    @ x = 'USER'
    @ ${x}
    'snail'
    @ ${'HO' + 'ME'}
    '/home/snail'


Environment Types
-----------------

Environment variables in xonsh are not limited to strings -- they can hold
any Python type: strings, numbers, lists, and arbitrary objects.  When a
variable is used as a subprocess argument, xonsh converts it to a string
automatically:

.. code-block:: xonshcon

    @ $MY_STR = 'hello'
    @ $MY_NUM = 42
    @ $MY_LIST = [1, 2, 3]
    @ showcmd echo $MY_STR $MY_NUM $MY_LIST
    ['echo', 'hello', '42', '[1, 2, 3]']

``$PATH`` is an :class:`~xonsh.environ.EnvPath` object -- a special list that makes it easy
to add and remove directories:

.. code-block:: xonshcon

    @ $PATH
    ['/usr/local/bin', '/usr/bin', '/bin']
    @ $PATH.append('/opt/mytools/bin')
    @ $PATH.insert(0, '$HOME/.local/bin')
    @ $PATH
    ['/home/snail/.local/bin', '/usr/local/bin', '/usr/bin', '/bin',
    '/opt/mytools/bin']

Any variable whose name ends in ``PATH`` or ``DIRS`` is automatically
treated as an :class:`~xonsh.environ.EnvPath`.

.. note:: In subprocess mode, referencing an undefined environment variable
          will produce an empty string.  In Python mode, however, a
          ``KeyError`` will be raised if the variable does not exist in the
          environment.


Xonsh Environment vs ``os.environ``
------------------------------------

Xonsh maintains its own environment (``@.env``) that is separate from
Python's ``os.environ``.  The two differ in important ways:

* **``os.environ``** is the standard OS process environment.  It only
  holds **string** values and is inherited by child processes
  automatically.  Libraries like ``subprocess``, ``os.system``, and any
  C code that calls ``getenv()`` all read from it.

* **``@.env``** is xonsh's rich environment.  It supports **typed
  values** -- lists for ``PATH`` variables, ints, bools, and even
  arbitrary Python objects.  It also provides defaults, validation,
  documentation, and the ``swap()`` context manager.

When you set ``$MY_VAR = [1, 2, 3]`` in xonsh, the value lives in
``@.env`` as a Python list.  But ``os.environ`` knows nothing about it
-- it still holds whatever was there when xonsh started.  This means
that child processes launched from Python code (e.g. via
``subprocess.run()``) won't see xonsh-side changes by default.

Subprocess commands launched through xonsh operators (``$()``, ``$[]``,
etc.) **do** see the xonsh environment because xonsh detypes and passes
it explicitly.

``$UPDATE_OS_ENVIRON``
^^^^^^^^^^^^^^^^^^^^^^

Set ``$UPDATE_OS_ENVIRON = True`` (default ``False``)
to keep ``os.environ`` in sync with
``@.env``.  When enabled, every change to the xonsh environment is
immediately written to ``os.environ`` (converted to a string).  This is
useful when you rely on third-party Python libraries that read
``os.environ`` directly:

.. code-block:: xonsh

    $UPDATE_OS_ENVIRON = True

    $DATABASE_URL = 'postgres://localhost/mydb'
    # Now os.environ['DATABASE_URL'] is also set,
    # so libraries like sqlalchemy will pick it up.

Note that setting ``$UPDATE_OS_ENVIRON = False`` only stops further
synchronization -- it does not revert ``os.environ`` to its original
state.


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

Callable Environment Variables
------------------------------

In some cases you may want an environment variable with a dynamically
created value.  Define a class with a ``__repr__`` method and assign an
instance to the variable -- xonsh will call ``repr()`` every time the
variable is accessed:

.. code-block:: xonshcon

    @ class Stamp:
         """Return current date as string representation."""
         def __repr__(self):
            return @.imp.datetime.datetime.now().isoformat()


    @ $DT = Stamp()
    @ $DT
    2024-11-11T11:11:22
    @ echo $DT
    2024-11-11T11:11:33
    @ env | grep DT
    DT=2024-11-11T11:11:44

Each access produces a fresh value, so the variable always reflects the
current state.

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
--------

* :doc:`envvars` -- full list of environment variables
* :doc:`strings` -- environment variable substitution in strings
* :doc:`launch` -- passing variables via ``-D`` at startup
* :doc:`xonshrc` -- setting variables in RC files
