**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Command pipelines that end in a callable alias are now interruptable with
  ``^C`` and the processes that are piped into the alais have their file handles
  closed. This should ensure that the entire pipeline is closed.

**Security:** None
