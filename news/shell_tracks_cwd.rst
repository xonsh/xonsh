**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed bug that prompt string and ``$PWD`` failed to track change in actual working directory if the
  invoked Python function happened to change it (e.g via ```os.chdir()```.  Fix is to update ``$PWD``
  after each command in ```BaseShell.default()```.

**Security:** None
