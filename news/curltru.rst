**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* The ``curl`` command will now be run in a thread, which prevents documents that
  do not end in a newline from writing over the next prompt and vice versa.

**Security:** None
