.. highlight:: bash

.. _python_virtual_environments:

===========================
Python Virtual Environments
===========================

The usual tools for creating Python virtual environments—``venv``, ``virtualenv``, ``pew``—don't play well with xonsh. We won't dig deeper into why it is so, but the general gist is that these tools are hacky and hard-coded for bash, zsh, and other mainstream shells.

Luckily, xonsh has its own virtual environments manager called **Vox**. Run to install Vox::

    $ xpip install xontrib-vox

Vox
===

First, load the vox xontrib::

    @ xontrib load vox

To create a new environment with vox, run ``vox new <envname>``::

    @ vox new myenv
    Creating environment...
    Environment "myenv" created. Activate it with "vox activate myenv".

The interpreter ``vox`` uses to create a virtualenv is configured via the ``$VOX_DEFAULT_INTERPRETER`` environment variable.

You may also set the interpreter used to create the virtual environment by passing it explicitly to ``vox new`` i.e.::

    @ vox new python2-env -p /usr/local/bin/python2

Under the hood, vox uses Python 3's ``venv`` module to create Python 3 virtualenvs. [this is the default]

If a Python 2 interpreter is chosen, it will use the Python 2 interpreter's ``virtualenv`` module.

By default, environments are stored in ``~/.virtualenvs``, but you can override it by setting the ``$VIRTUALENV_HOME`` environment variable.

To see all existing environments, run ``vox list``::

    @ vox list
    Available environments:
        eggs
        myenv
        spam

To activate an environment, run ``vox activate <envname>``::

    @ vox activate myenv
    Activated "myenv".

Instead of ``activate``, you can call ``workon`` or ``enter``.

If you want to activate an environment which is stored somewhere else (maybe because it was created by another tool) you can pass to ``vox activate`` a path to a virtual environment::

    @ vox activate /home/user/myenv
    Activated "/home/user/myenv".

To exit the currently active environment, run ``vox deactivate`` or ``vox exit``::

    @ vox deactivate
    Deactivated "myenv".

To remove an environment, run ``vox remove <envname>``::

    @ vox remove myenv
    Environment "myenv" removed.

Instead of ``remove``, you can call ``rm``, ``delete``, or ``del``.

To see all available commands, run ``vox help``, ``vox --help``, or ``vox -h``::

    Vox is a virtual environment manager for xonsh.

    Available commands:
        vox new <env>
            Create new virtual environment in $VIRTUALENV_HOME

        vox activate (workon, enter) <env>
            Activate virtual environment

        vox deactivate (exit)
            Deactivate current virtual environment

        vox list (ls)
            List environments available in $VIRTUALENV_HOME

        vox remove (rm, delete, del) <env> <env2> ...
            Remove virtual environments

        vox help (-h, --help)
            Show help


``virtualenv`` like prompt
--------------------------
Although it's included in the default prompt, you can customize your prompt
to automatically update in the same way as ``virtualenv``.

Simply add the ``'{env_name}'`` variable to your ``$PROMPT``::

    $PROMPT = '{env_name: {}}' + restofmyprompt

Note that you do **not** need to load the ``vox`` xontrib for this to work.
For more details see :ref:`customprompt`.


Automatically Switching Environments
------------------------------------

Automatic environment switching based on the current directory is managed with the ``autovox`` xontrib (``xontrib load autovox``). Third-party xontribs may register various policies for use with autovox. Pick and choose xontribs that implement policies that match your work style.

Implementing policies is easy! Just register with the ``autovox_policy`` event and return a ``Path`` if there is a matching venv. For example, this policy implements handling if there is a ``.venv`` directory in the project::

    @events.autovox_policy
    def dotvenv_policy(path, **_):
        venv = path / '.venv'
        if venv.exists():
            return venv

Note that you should only return if there is an environment for this directory exactly. Scanning parent directories is managed by autovox. You should also make the policy check relatively cheap. (Local IO is ok, but probably shouldn't call out to network services.)
