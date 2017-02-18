**Added:** None

**Changed:**

* ``Shell.stype`` has been renamed to ``Shell.shell_type``.
* The configuration wizard now displays the proper control sequence to leave
  the wizard at the to start of the wizard itself. Note that this is Ctrl+D for
  readline and Ctrl+C for prompt-toolkit.

**Deprecated:** None

**Removed:** None

**Fixed:**

* ``Shell.shell_type`` is now properly set to the same value as ``$SHELL_TYPE``.

**Security:** None
