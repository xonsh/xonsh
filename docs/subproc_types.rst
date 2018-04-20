.. _subproc_types:

**********************
Subprocess Types Table
**********************
Xonsh has a few different ways to launch subprocesses, each with their own
unique interface depending on your need. The following table is a quick reference
for the different suprocesses. The columns have the following meaning:

:Type: The syntax for an example subprocess ``cmd``.
:Output: Whether the output is streamed to stdout/stderr.  If "captured", the output is
    not streamed as the ``cmd`` runs. If "uncaptured", the output is streamed.
:Returns: The type of the object returned by the subprocess executions. For example,
    if you were to run ``p = $(cmd)``, the return column gives the type of ``p``.
:Notes: Any comments about the subprocess.

.. list-table::
    :header-rows: 1
    :align: center

    * - Type
      - Output
      - Returns
      - Notes
    * - ``cmd``
      - Uncaptured
      - ``HiddenCommandPipeline``
      - The same as ``![cmd]``
    * - ``![cmd]``
      - Uncaptured
      - ``HiddenCommandPipeline``
      -
    * - ``$[cmd]``
      - Uncaptured
      - ``None``
      -
    * - ``!(cmd)``
      - Captured
      - ``CommandPipeline``
      -
    * - ``$(cmd)``
      - Captured
      - ``str``
      - stdout is returned


