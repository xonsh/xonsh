**Added:**

* <news item>

**Changed:**

* With ``$THREAD_SUBPROCS=False``: When a callable alias is executed with ``![]``, its standard output and standard error are no longer captured. This is because a separate thread is required in order to both capture the output and stream it to the terminal while the alias is running.

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* With ``$THREAD_SUBPROCS=False``: When ``cd`` is used with an invalid directory, the error message is now correctly displayed.

**Security:**

* <news item>
