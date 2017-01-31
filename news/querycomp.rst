**Added:**

* New ``$COMPLETION_QUERY_LIMIT`` environment variable for setting the
  number of completions above which the user will be asked if they wish to
  see the potential completions.

**Changed:** None

**Deprecated:** None

**Removed:** None

**Fixed:**

* Readline backend would not ask the user to confirm the printing of completion
  options if they numbered above a certain value. Instead they would be dumped to
  the screen. This has been fixed.

**Security:** None
