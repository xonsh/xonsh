**Added:**

* New argument ``expand_user=True`` to ``tools.expand_path``.

**Changed:**

* Move ``built_ins.expand_path`` to ``tools.expand_path``.
* Rename ``tools.expandpath`` to ``tools._expandpath``.

**Deprecated:** None

**Removed:** None

**Fixed:**

* Introduce path expansion in ``is_writable_file`` to fix
  ``$XONSH_TRACEBACK_LOGFILE=~/xonsh.log``.

**Security:** None
