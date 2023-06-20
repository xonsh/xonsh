Bash to Xonsh Translation Guide
================================
As you have probably figured out by now, xonsh is not ``sh``-lang compliant.
If your muscles have memorized all of the Bash prestidigitations, this page
will help you put a finger on how to do the equivalent task in xonsh.

For shell scripts, the recommended file extension is ``xsh``, and shebang
line is ``#!/usr/bin/env xonsh``.

.. list-table::
    :widths: 30 30 40
    :header-rows: 1

    * - Bash
      - Xonsh
      - Notes
    * - ``echo --arg="val"``

        ``echo {}``

        ``echo \;``

      - ``echo --arg "val"``

        ``echo "{}"``

        ``echo ";"``

      - Read `Subprocess Strings <https://xon.sh/tutorial_subproc_strings.html>`_ tutorial
        to understand how strings become arguments in xonsh.
        There is no notion of an escaping character in xonsh like the backslash (``\``) in bash.
        Single or double quotes can be used to remove the special meaning of certain
        characters, words or brackets.
    * - ``$NAME`` or ``${NAME}``
      - ``$NAME``
      - Look up an environment variable by name.
    * - ``export NAME=Peter``
      - ``$NAME = 'Peter'``
      - Setting an environment variable. See also :ref:`$UPDATE_OS_ENVIRON <update_os_environ>`.
    * - ``unset NAME``
      - ``del $NAME``
      - Unsetting/deleting an environment variable.
    * - ``echo "$HOME/hello"``
      - ``echo "$HOME/hello"``
      - Construct an argument using an environment variable.
    * - ``something/$SOME_VAR/$(some_command)``
      - ``@('something/' + $SOME_VAR + $(some_command).strip())``
      - Concatenate a variable or text with the result of running a command.
    * - ``echo 'my home is $HOME'``
      - ``echo @("my home is $HOME")``
      - Escape an environment variable from expansion.
    * - ``${!VAR}``
      - ``${var or expr}``
      - Look up an environment variable via another variable name. In xonsh,
        this may be any valid expression.
    * - ``ENV1=VAL1 command``
      - ``$ENV1=VAL1 command``

        or ``with ${...}.swap(ENV1=VAL1): command``
      - Set temporary environment variable(s) and execute the command.
        Use the second notation with an indented block to execute many commands in the same context.
    * - ``alias ll='ls -la'``
      - ``aliases['ll'] = 'ls -la'``
      - Alias in xonsh could be a subprocess command as a string or list of arguments or any Python function.
    * - ``$(cmd args)`` or ```cmd args```
      - ``@$(cmd args)``
      - Command substitution (allow the output of a command to replace the
        command itself).  Tokenizes and executes the output of a subprocess
        command as another subprocess.
    * - ``v=`echo 1```
      - ``v=$(echo 1)``
      - In bash, backticks mean to run a captured subprocess - it's ``$()`` in xonsh. Backticks in xonsh
        mean regex globbing (i.e. ``ls `/etc/pass.*```).
    * - ``echo -e "\033[0;31mRed text\033[0m"``
      - ``printx("{RED}Red text{RESET}")``
      - Print colored text as easy as possible.
    * - ``shopt -s dotglob``
      - ``$DOTGLOB = True``
      - Globbing files with ``*`` or ``**`` will also match dotfiles, or those ‘hidden’ files whose names
        begin with a literal `.`. Such files are filtered out by default like in bash.
    * - ``if [ -f "$FILE" ];``
      - ``p'/path/to/file'.exists()`` or ``pf'{file}'.exists()``
      - Path objects can be instantiated and checked directly using p-string syntax.
    * - ``set -e``
      - ``$RAISE_SUBPROC_ERROR = True``
      - Cause a failure after a non-zero return code. Xonsh will raise a
        ``supbrocess.CalledProcessError``.
    * - ``set -x``
      - ``trace on`` and ``$XONSH_TRACE_SUBPROC = True``
      - Turns on tracing of source code lines during execution.
    * - ``&&``
      - ``&&`` or ``and``
      - Logical-and operator for subprocesses.
    * - ``||``
      - ``||`` as well as ``or``
      - Logical-or operator for subprocesses.
    * - ``$$``
      - ``os.getpid()``
      - Get PID of the current shell.
    * - ``$?``
      - ``_.rtn``
      - Returns the exit code, or status, of the previous command. The underscore ``_`` is working
        in the prompt mode. To get the exit code of the command in xonsh script
        use captured subprocess ``!().rtn``.
    * - ``!$``
      - ``__xonsh__.history[-1, -1]``
      - Get the last argument of the last command
    * - ``$<n>``
      - ``$ARG<n>``
      - Command line argument at index ``n``,
        so ``$ARG1`` is the equivalent of ``$1``.
    * - ``$@``
      - ``$ARGS``
      - List of all command line argument and parameter strings.
    * - ``while getopts``
      - ``import argparse``
      - Start from `argparse <https://docs.python.org/3/library/argparse.html>`_ library to describe
        the command line arguments in your script. Next try
        `xontrib-argcomplete <https://github.com/anki-code/xontrib-argcomplete>`_ to activate
        tab completion for your script.
    * - ``complete``
      - ``completer list``
      - As with many other shells, xonsh ships with the ability to complete partially-specified arguments
        upon hitting the “tab” key.
    * - OhMyBash or BashIt
      - `Xontribs <https://xon.sh/xontribs.html>`_
      - Xontributions, or ``xontribs``, are a set of tools and conventions for extending the functionality
        of xonsh beyond what is provided by default.
    * - Display completions as list
      - ``$COMPLETIONS_DISPLAY = 'readline'``
      - Display completions will emulate the behavior of readline.
    * - ``docker run -it bash``
      - ``docker run -it xonsh/xonsh:slim``
      - Xonsh publishes a handful of containers, primarily targeting CI and automation use cases.
        All of them are published on `Docker Hub <https://hub.docker.com/u/xonsh>`_.
    * - ``exit 1``
      - ``exit(1)``
      - Exiting from the current script.

To understand how xonsh executes the subprocess commands try
to set :ref:`$XONSH_TRACE_SUBPROC <xonsh_trace_subproc>` to ``True``:

.. code-block:: console

    >>> $XONSH_TRACE_SUBPROC = True
    >>> echo $(echo @('hello')) @('wor' + 'ld') | grep hello
    TRACE SUBPROC: (['echo', 'hello'],)
    TRACE SUBPROC: (['echo', 'hello\n', 'world'], '|', ['grep', 'hello'])

If after time you still try to type ``export``, ``unset`` or ``!!`` commands
there are the `bashisms <https://github.com/xonsh/xontrib-bashisms>`_
and `sh <https://github.com/anki-code/xontrib-sh>`_ xontribs.
