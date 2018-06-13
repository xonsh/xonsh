**Added:** None

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Fixed issue where xonsh would fail to properly return the terminal prompt
  (and eat up 100% CPU) after a failed subprocess command in interactive mode
  if ``$RAISE_SUBPROC_ERROR = True``.

**Security:** None
