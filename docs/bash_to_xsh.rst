Bash to Xonsh Translation Guide
================================
As you have probably figured out by now, xonsh is not ``sh``-lang compliant.
If your muscles have memorized all of the Bash prestidigitations, this page
will help you put a finger on how to do the equivelent task in xonsh.

.. list-table::
    :widths: 30 30 40
    :header-rows: 1

    * - Bash
      - Xonsh
      - Notes
    * - ``$NAME`` or ``${NAME}``
      - ``$NAME``
      - Look up an environment variable by name.
    * - ``echo "$HOME/hello"``
      - ``echo "$HOME/hello"``
      - Construct an argument using an environment variable.
    * - ``something/$SOME_VAR/$(some_command)``
      - ``@('something/' + $SOME_VAR + $(some_command).strip())``
      - Concatenate a variable or text with the result of running a command.
    * - ``${!VAR}``
      - ``${var or expr}``
      - Look up an environment variable via another variable name. In xonsh,
        this may be any valid expression.
    * - ``$(cmd args)`` or ```cmd args```
      - ``@$(cmd args)``
      - Command substitution (allow the output of a command to replace the
        command itself).  Tokenizes and executes the output of a subprocess
        command as another subprocess.
    * - ``set -e``
      - ``$RAISE_SUBPROC_ERROR = True``
      - Cause a failure after a non-zero return code. Xonsh will raise a
        ``supbrocess.CalledProcessError``.
    * - ``set -x``
      - ``trace on``
      - Turns on tracing of source code lines during execution.
    * - ``&&``
      - ``and`` or ``&&``
      - Logical-and operator for subprocesses.
    * - ``||``
      - ``or`` as well as ``||``
      - Logical-or operator for subprocesses.
    * - ``$?``
      - ``_.rtn``
      - Returns the exit code, or status, of the previous command.
    * - ``N=V command``
      - ``with ${...}.swap(N=V): command``
      - Set temporary environment variable(s) and execute for command.
        Use an indented block to execute many commands in the same context.

