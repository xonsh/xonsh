**Added:**

* JsonHistory: added ``history gc --force`` switch to allow user to override above warning.
* JsonHistoryGC: display following warning when garbage collection would delete "too" much data and don't delete anything.
  
  "Warning: History garbage collection would discard more history ({size_over} {units}) than it would keep ({limit_size}).\n"
  "Not removing any history for now. Either increase your limit ($XONSH_HIST_SIZE), or run ``history gc --force``.",
   
  It is displayed when the amount of history on disk is more than double the limit configured (or defaulted) for $XONSH_HIST_SIZE.

**Changed:**

* Garbage collection avoids deleting history and issues a warning instead if existing history is more than double the comfigured limit.
  This protects active users who might have accumulated a lot of history while a bug was preventing garbage collection.  The warning
  will be displayed each time Xonsh is started until user takes action to reconcile the situation.
* ``tests\test_integrations.py`` no longer runs with XONSH_DEBUG=1 (because new, debug-only progress messages from history were breaking it).

**Deprecated:**

* <news item>

**Removed:**

* <news item>

**Fixed:**

* JsonHistory.files(): Now once again enumerates history files from the directory.  This has been broken for about 2 years.
* JsonHistory.run_gc(): Don't busy loop while waiting for history garbage collection to complete, sleep a bit instead.
  This does much to keep Xonsh ptk_shell responsive when dealing with very large history on disk. 

**Security:**

* <news item>
