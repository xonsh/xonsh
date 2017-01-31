**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Backgrounding a running process (^Z) now restores ECHO mode to the terminal
  in cases where the subprocess doesn't properly restore itself. A major instance
  of this behaviour is Python's interactive interpreter.

**Security:** None
