.. highlight:: bash

.. _python_virtual_environments:

====================
Virtual Environments
====================

Python virtual environments let you isolate a project's dependencies from
the system Python, and xonsh works with the usual tools for creating them.
Whichever tool you pick, the :ref:`xcontext <aliases-xcontext>` command
will always tell you which interpreter, ``pip``, and environment variables
are in effect right now — handy when something isn't resolving where you
expected.

``virtualenv``
==============

`virtualenv <https://virtualenv.pypa.io/>`_ ships with a native xonsh
activator, so creating and entering an environment takes just two steps:

.. code-block:: xonshcon

    @ virtualenv myenv
    @ source myenv/bin/activate.xsh
    (myenv) @

To leave the environment, run ``deactivate``.


``vox``
=======

xonsh works with the usual Python virtual environment tools — ``venv``,
``virtualenv``, ``pew`` — and on top of that ships its own environments
manager called **Vox**. Vox is an xontrib that makes creating, listing,
activating, and removing virtualenvs feel natural right inside the shell,
so you don't have to leave the REPL or remember a separate activation
script per project.

Install and load Vox:

.. code-block:: xonshcon

    @ xpip install xontrib-vox
    @ xontrib load vox

To create a new environment with vox, run ``vox new <envname>``:


.. code-block:: xonshcon

    @ vox new myenv
    Creating environment...
    Environment "myenv" created. Activate it with "vox activate myenv".

The interpreter ``vox`` uses to create a virtualenv is configured via the ``$VOX_DEFAULT_INTERPRETER`` environment variable.

You may also set the interpreter used to create the virtual environment by passing it explicitly to ``vox new`` i.e.:

.. code-block:: xonshcon

    @ vox new python2-env -p /usr/local/bin/python2

Under the hood, vox uses Python 3's ``venv`` module to create Python 3 virtualenvs. [this is the default]

If a Python 2 interpreter is chosen, it will use the Python 2 interpreter's ``virtualenv`` module.

By default, environments are stored in ``~/.virtualenvs``, but you can override it by setting the ``$VIRTUALENV_HOME`` environment variable.

To see all existing environments, run ``vox list``:

.. code-block:: xonshcon

    @ vox list
    Available environments:
        eggs
        myenv
        spam

To activate an environment, run ``vox activate <envname>``:

.. code-block:: xonshcon

    @ vox activate myenv
    Activated "myenv".

Instead of ``activate``, you can call ``workon`` or ``enter``.

If you want to activate an environment which is stored somewhere else (maybe because it was created by another tool) you can pass to ``vox activate`` a path to a virtual environment:


.. code-block:: xonshcon

    @ vox activate /home/user/myenv
    Activated "/home/user/myenv".

To exit the currently active environment, run ``vox deactivate`` or ``vox exit``:

.. code-block:: xonshcon

    @ vox deactivate
    Deactivated "myenv".

To remove an environment, run ``vox remove <envname>``:

.. code-block:: xonshcon

    @ vox remove myenv
    Environment "myenv" removed.

Instead of ``remove``, you can call ``rm``, ``delete``, or ``del``.

To see all available commands, run ``vox help``, ``vox --help``, or ``vox -h``.

``virtualenv`` like prompt
--------------------------
Although it's included in the default prompt, you can customize your prompt
to automatically update in the same way as ``virtualenv``.

Simply add the ``'{env_name}'`` variable to your ``$PROMPT``:

.. code-block:: xonshcon

    @ $PROMPT = '{env_name: {}}' + restofmyprompt

Note that you do **not** need to load the ``vox`` xontrib for this to work.
For more details see :ref:`customprompt`.


Automatically Switching Environments
------------------------------------

Automatic environment switching based on the current directory is managed with the ``autovox`` xontrib (``xontrib load autovox``). Third-party xontribs may register various policies for use with autovox. Pick and choose xontribs that implement policies that match your work style.

Implementing policies is easy! Just register with the ``autovox_policy`` event and return a ``Path`` if there is a matching venv. For example, this policy implements handling if there is a ``.venv`` directory in the project:

.. code-block:: xonsh

    @events.autovox_policy
    def dotvenv_policy(path, **_):
        venv = path / '.venv'
        if venv.exists():
            return venv

Note that you should only return if there is an environment for this directory exactly. Scanning parent directories is managed by autovox. You should also make the policy check relatively cheap. (Local IO is ok, but probably shouldn't call out to network services.)


See also
========

* :ref:`aliases-xcontext` — inspect the interpreter, ``pip``, and active
  environment variables of the current session.
* :ref:`customprompt_ref` — customize ``{env_name}``, ``{env_prefix}``,
  and ``{env_postfix}`` to control how the active environment appears in
  the prompt.
