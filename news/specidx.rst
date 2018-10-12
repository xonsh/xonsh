**Added:**

* ``SubprocSpec`` has a new ``pipeline_index`` integer attribute that indicates
  the commands position in a pipeline. For example, in

  .. code-block:: sh

    p = ![ls -l | grep x]

  The ``ls`` command would have a pipeline index of 0
  (``p.specs[0].pipeline_index == 0``) and ``grep`` would have a pipeline index
  of 1 (``p.specs[1].pipeline_index == 1``).  This may be usefule in callable
  alaises which recieve the spec as an argument.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
