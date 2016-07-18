.. highlight:: bash

.. _python_virtual_environments:

===========================
Python Virtual Environments
===========================

The usual tools for creating Python virtual environments—``venv``, ``virtualenv``, ``pew``—don't play well with xonsh. We won't dig deeper into why it is so, but the general gist is that these tools are hacky and hard-coded for bash, zsh, and other mainstream shells.

Luckily, xonsh ships with its own virtual environments manager called **Vox**.

Vox
===

To create a new environment with vox, run ``vox new <envname>``::

    $ vox new myenv
    Creating environment...
    Environment "myenv" created. Activate it with "vox activate myenv".

By default, environments are stored in ``~/.virtualenvs``, but you can override it by setting the ``$VIRTUALENV_HOME`` environment variable.

To see all existing environments, run ``vox list``::

    $ vox list
    Available environments:
        eggs
        myenv
        spam

To activate an environment, run ``vox activate <envname>``::

    $ vox activate myenv
    Activated "myenv".

Instead of ``activate``, you can call ``workon`` or ``enter``.

To exit the currently active environment, run ``vox deactivate`` or ``vox exit``::

    $ vox deactivate
    Deactivated "myenv".

To remove an environment, run ``vox remove <envname>``::

    $ vox remove myenv
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
            List all available environments

        vox remove (rm, delete, del) <env> <env2> ...
            Remove virtual environments

        vox help (-h, --help)
            Show help
