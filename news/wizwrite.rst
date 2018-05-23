**Added:**

* Wizard ``FileInsterter`` node class now has ``dumps()`` method for
  converting a mapping to a string to insert in a file.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue with ``xonfig wizard`` writer failing to write valid run control
  files for environment variables that are containter types. In particular,
  the storage of ``$XONSH_HISTORY_SIZE`` has been fixed.

**Security:** None
