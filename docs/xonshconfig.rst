Static Configuration File
=========================
In addition to the run control file, xonsh allows you to have a static config file.
This JSON-formatted file lives at ``$XONSH_CONFIG_DIR/config.json``, which is
normally ``~/.config/xonsh/config.json``. The purpose of this file is to allow
users to set runtime parameters *before* anything else happens. This inlcudes 
loading data from various foreign shells or setting critical environment
variables.

This is a dictionary or JSON object at its top-level.  It has the following 
top-level keys.  All top-level keys are optional.

``env``
--------
This is a simple string-keyed dictionary that lets you set environment 
variables. For example, 

.. code:: json

    {"env": {
     "EDITOR": "xo",
     "PAGER": "more"
     }
    }


``foreign_shells``
--------------------
This is a list (JSON Array) of dicts (JSON objects) that represent the
foreign shells to inspect for extra start up information, such as environment
variables, aliases, and foreign shell functions. The suite of data gathered 
may be expanded in the future.  Each shell dictionary unpacked and passed into
the ``xonsh.foreign_shells.foreign_shell_data()`` function. Thus these 
dictionaries have the following structure:

:shell: *str, required* - The name or path of the shell, such as "bash" or "/bin/sh".
:interactive: *bool, optional* - Whether the shell should be run in interactive mode.
    ``default=true``
:login: *bool, optional* - Whether the shell should be a login shell.
    ``default=false``
:envcmd: *str, optional* - The command to generate environment output with.
    ``default="env"``
:aliascmd: *str, optional* - The command to generate alais output with.
    ``default="alias"``
:extra_args: *list of str, optional* - Addtional command line options to pass 
    into the shell. ``default=[]``
:currenv: *dict or null, optional* - Manual override for the current environment.
    ``default=null``
:safe: *bool, optional* - Flag for whether or not to safely handle exceptions 
    and other errors. ``default=true``
:prevcmd: *str, optional* - An additional command or script to run before 
    anything else, useful for sourcing and other commands that may require 
    environment recovery. ``default=''``
:postcmd: *str, optional* - A command to run after everything else, useful for
    cleaning up any damage that the ``prevcmd`` may have caused. ``default=''``
:funcscmd: *str or None, optional* - This is a command or script that can be 
    used to determine the names and locations of any functions that are native
    to the foreign shell. This command should print *only* a whitespace 
    separated sequence of pairs function name & filenames where the functions
    are defined. If this is None (null), then a default script will attempted
    to be looked up based on the shell name. Callable wrappers for these 
    functions will be returned in the aliases dictionary. ``default=null``
:sourcer: *str or None, optional* - How to source a foreign shell file for 
    purposes of calling functions in that shell. If this is None, a default 
    value will attempt to be looked up based on the shell name. ``default=null``

Some examples can be seen below:

.. code:: json

    # load bash then zsh
    {"foreign_shells": [
        {"shell": "/bin/bash"},
        {"shell": "zsh"}
     ]
    }

    # load bash as a login shell with custom rcfile
    {"foreign_shells": [
        {"shell": "bash", 
         "login": true, 
         "extra_args": ["--rcfile", "/path/to/rcfile"]
         }
     ]
    }

    # disable all foreign shell loading via an empty list
    {"foreign_shells": []}


Putting it all together
-----------------------
The following ecample shows a fully fleshed out config file.

:download:`Download config.json <xonshconfig.json>`

.. include:: xonshconfig.json
    :code: json

