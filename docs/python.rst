.. _python:

======
Python
======

Xonsh is built on top of Python and Python code can be executed natively
alongside shell commands. This page collects notes on how Python-specific
behaviour interacts with the shell.

Python versions support policy
==============================

Xonsh adopts `NEP-0029 <https://numpy.org/neps/nep-0029-deprecation_policy.html>`_ in supporting Python versions.
Simply speaking a minor Python release (X.*) will be supported for 42 months from its date of initial release.
Since Python has adopted yearly release cycle, most of the time,
the latest 4 minor versions of Python would be supported at any given time.


.. _import_local_modules:

Importing Python modules from a local directory
===============================================

The modules available for import in a given ``xonsh`` session depend on what's
available in ``sys.path``. If you want to be able to import a module that
resides in the current directory, ensure that there is an empty string as the
first element of your ``sys.path``:

.. code-block:: xonshcon

   @ import sys
   @ sys.path.insert(0, '')


Inline scripting
================

Inline import
-------------

Use ``@.imp`` as an inline importer (xonsh >= 0.18.2) — modules are looked
up lazily without a preceding ``import`` statement:

.. code-block:: xonshcon

   @ @.imp.json.loads($(echo '{"a":1}'))
   {'a': 1}

   @ @.imp.datetime.datetime.now().isoformat()
   '2024-02-12T15:29:57.125696'

   @ @.imp.hashlib.md5(b'Hello world').hexdigest()
   '3e25960a79dbc69b674cd4ec67a72c62'

Autocompletion works too — e.g. ``@.imp.date<TAB>``.


Inline statements
-----------------

Use ``$[...]`` (or ``$(...)``) to embed subprocess statements directly
inside Python expressions — loops, comprehensions, conditionals, and
context managers all compose naturally:

.. code-block:: xonshcon

   @ for i in range(1, 5): $[echo @(i)]

   @ [$[echo @(i)] for i in range(1, 5)]

   @ if $(which vim): $[echo vim]

   @ $[echo vim] if $(which vim) else $[echo vi]

   @ with @.env.swap(QWE=1): $[bash -c 'echo $QWE']

   @ $A=1 $B=2 bash -c 'echo $A $B'


String tricks
=============

Triple quotes
-------------

To avoid escape characters (``echo "\"hello\""``) and keep strings readable,
use triple quotes:

.. code-block:: xonshcon

   @ echo """{"hello":'world'}"""
   {"hello":'world'}


f-strings in commands
---------------------

f-strings work both inside ``@(...)`` and standalone as arguments
(xonsh >= 0.23.0):

.. code-block:: xonshcon

   @ echo @(f'Hello {$HOME}')
   Hello /home/snail

   @ echo f'Hello {$HOME}'
   Hello /home/snail


Walrus operator in action
=========================

Python's walrus operator ``:=`` (`PEP 572 <https://peps.python.org/pep-0572/>`_)
lets you capture a value inline and reuse it later.

In subprocess:

.. code-block:: xonshcon

   @ echo Hello @(_name := input('Name: '))  # use ``_`` to keep the env clean
   @ echo Hello again @(_name)
   Name: Mike
   Hello Mike
   Hello again Mike

Works with JSON/struct output too — decorators like ``@json`` return Python
objects which the walrus captures for reuse:

.. code-block:: xonshcon

   @ (servers := $(@json echo '["srv1", "srv2"]'))
   ['srv1', 'srv2']

   @ echo @(servers[0])
   srv1


Shadowing between shell commands and Python names
==================================================

Because xonsh parses Python-mode first, a bare name that resolves as a
Python built-in is evaluated as Python rather than run as a shell
command. Classic collisions: ``id``, ``zip``, ``dir``, ``import``.

.. code-block:: xonshcon

   @ id
   <built-in function id> # Python built-in, not /usr/bin/id

Workarounds:

* **Flip the experimental toggle**
  `$XONSH_BUILTINS_TO_CMD <envvars.html#XONSH_BUILTINS_TO_CMD>`_ — when
  set, bare built-in names are run as subprocess commands if a matching
  alias or executable exists, falling back to the Python built-in
  otherwise. The same switch is also useful on Windows for ``dir`` (see
  `platforms <platforms.html#name-space-conflicts>`_).
* **Change the case**: ``Zip`` or ``ZIP`` — Python names are case-sensitive,
  so ``Zip`` misses the built-in and falls through to a command lookup.
  On case-insensitive filesystems (macOS default, Windows) ``Zip`` then
  resolves to the ``zip`` executable. On case-sensitive filesystems
  (typical Linux) this only works if such a name exists in ``$PATH`` —
  use a different workaround below.
* **Force subprocess mode** with ``$[...]``, ``$(...)`` or a redirect:
  ``$[id]``, ``$(id)``.
* **Alias it under a different name**: ``aliases['ids'] = 'id'``.
* **Use `xontrib-abbrevs`** to auto-expand on space.


See also: `xonsh-cheatsheet <https://github.com/anki-code/xonsh-cheatsheet>`_
for more copy-pastable examples.
