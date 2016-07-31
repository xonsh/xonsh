**Added:**

* ``_hist_get`` that uses generators to filter and fetch
  the history commands of each session.

* ``-n`` option to the show subcommand to choose
  to numerate the commands.

**Changed:**

* ``_hist_show`` now uses ``_hist_get`` to print out the commands.

**Deprecated:** None

**Removed:** None

**Fixed:**

* ``_zsh_hist_parser`` not parsing history files without timestamps.

**Security:** None
