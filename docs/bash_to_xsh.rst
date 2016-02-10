Bash to Xonsh Translation Guide
================================
As you have probably figures out by now, Bash is not ``sh``-lang compliant.
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
    * - ``${${VAR}}``
      - ``${var or expr}``
      - Look up an environment variable via another variable name. In xonsh, 
        this may be any valid expression.
    * - ``$(cmd args)`` or ```cmd args```
      - ``$(cmd args)``
      - Use the ``$()`` operator to capture subprocesses as strings. Bash's
        version of (now-deprecated) backticks is not supported. Note that 
        Bash will automatically tokenize the string, while xonsh just returns 
        a str of stdout.
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
