**Added:** None

**Changed:**

* The ``xontrib`` command is now flagged as unthreadable and will be
  run on the main Python thread. This allows xontribs to set signal
  handlers and other operations that require the main thread.

**Deprecated:** None

**Removed:** None

**Fixed:** None

**Security:** None
