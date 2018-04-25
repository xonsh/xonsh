**Added:** None

**Changed:**

* ``CommandPipeline.proc`` may now be ``None``, to accomodate when the process
  fails to even start (i.e. a missing command or incorrect permisions).

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with ``$XONSH_SHOW_TRACEBACK`` not being respected in subprocess
  mode when the command could not be found or had incorrect permissions.

**Security:** None
